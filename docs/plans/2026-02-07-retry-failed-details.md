# Retry Failed BNE Detail Pages

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Re-enqueue vagas that got 403 during detail fetching so they're retried with a fresh IP, instead of being permanently skipped.

**Architecture:** Extract the detail-fetching loop into a helper method `_fetch_details`. Call it in a `while` loop: each pass collects failed vagas, and if progress was made (at least 1 success), retries the failures. Stops when no progress or no failures remain.

**Tech Stack:** Pure Python refactor, no new dependencies.

**Design decisions:**
- Retry stops when a pass makes **zero progress** (all vagas failed) — prevents infinite loops.
- Max 3 retry passes as a safety cap.
- Each retry pass starts with a fresh browser (new IP).
- The `ip_rotations` / `consecutive_errors` / proxy activation logic inside the loop stays unchanged — retries are an outer layer.

---

### Task 1: Extract `_fetch_details` helper and add retry loop

**Files:**
- Modify: `src/vagas/spiders/bne.py:323-374`

**Step 1: Replace the detail-fetching block**

Replace lines 331–372 (the `fetched = 0` through `await asyncio.sleep(...)`) with:

```python
            fetched, pending = await self._fetch_details(page, need_detail, _restart_browser)

            # Retry failed vagas with fresh IPs (max 3 retry passes)
            max_retry_passes = 3
            for retry in range(max_retry_passes):
                if not pending:
                    break
                log.info("[%s] retrying %d failed details (pass %d/%d)",
                         self.name, len(pending), retry + 1, max_retry_passes)
                await _restart_browser(block_resources=True)
                newly_fetched, pending = await self._fetch_details(page, pending, _restart_browser)
                if newly_fetched == 0:
                    log.info("[%s] retry pass made no progress, stopping", self.name)
                    break
                fetched += newly_fetched

            log.info("[%s] details fetched: %d/%d", self.name, fetched, len(all_vagas))
```

**Step 2: Add `_fetch_details` method to BNESpider (before `crawl`)**

```python
    async def _fetch_details(self, page, vagas: list, _restart_browser) -> tuple[int, list]:
        """Fetch detail pages. Returns (success_count, failed_vagas)."""
        fetched = 0
        failed: list = []
        consecutive_errors = 0
        ip_rotations = 0
        max_rotations = 5
        gave_up = False

        for vaga in vagas:
            try:
                resp = await page.goto(vaga.url, wait_until="domcontentloaded")
                if resp and resp.status >= 400:
                    raise Exception(f"HTTP {resp.status}")
                await asyncio.sleep(1)
                detail_html = await page.content()
            except Exception as e:
                log.debug("[%s] detail failed %s: %s", self.name, vaga.url, e)
                failed.append(vaga)
                consecutive_errors += 1
                if self._record_failure():
                    await _restart_browser(block_resources=True)
                    consecutive_errors = 0
                elif self._proxy_active and consecutive_errors >= 3:
                    ip_rotations += 1
                    if ip_rotations > max_rotations:
                        log.warning("[%s] %d IP rotations reached, deferring remaining to retry",
                                    self.name, max_rotations)
                        failed.extend(vagas[vagas.index(vaga) + 1:])
                        gave_up = True
                        break
                    log.info("[%s] rotating IP (%d/%d)",
                             self.name, ip_rotations, max_rotations)
                    await _restart_browser(block_resources=True)
                    consecutive_errors = 0
                elif consecutive_errors >= 10:
                    log.warning("[%s] %d consecutive failures (no proxy), deferring to retry",
                                self.name, consecutive_errors)
                    failed.extend(vagas[vagas.index(vaga) + 1:])
                    gave_up = True
                    break
                continue

            consecutive_errors = 0
            ip_rotations = 0
            self._record_success()
            self.parse_detail(detail_html, vaga)
            fetched += 1
            log.debug("[%s] detail fetched: %s", self.name, vaga.url)
            await asyncio.sleep(3 + random.uniform(1, 2))

        return fetched, failed
```

**Step 3: Run tests**

Run: `pytest tests/test_proxy.py tests/test_models.py tests/test_filters.py -v`
Expected: all PASS (no behavioral changes to tested code)

**Step 4: Manual smoke test**

Run: `vagas bne --debug --dry-run`
Expected: See retry passes in logs when details fail. Example:
```
[bne] retrying 63 failed details (pass 1/3)
[bne] rotating IP (1/5)
...
[bne] details fetched: 240/485
```
