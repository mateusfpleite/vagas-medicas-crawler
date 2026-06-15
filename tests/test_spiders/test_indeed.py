import json

import pytest

from vagas.spiders.indeed import IndeedSpider


def _make_mosaic_result(**overrides):
    """Factory for a single mosaic result dict."""
    base = {
        "displayTitle": "Médico Clínico Geral",
        "company": "Hospital São Luiz",
        "formattedLocation": "São Paulo, SP",
        "jobLocationCity": "São Paulo",
        "jobLocationState": "SP",
        "jobkey": "abc123def456",
        "normTitle": "Medico",
        "jobTypes": ["Efetivo/CLT"],
        "salarySnippet": {
            "currency": "BRL",
            "text": "R$ 15.000 – R$ 30.000 por mês",
        },
        "extractedSalary": {"min": 15000, "max": 30000, "type": "MONTHLY"},
        "snippet": "<ul><li>Experiência em clínica médica</li></ul>",
        "taxonomyAttributes": [
            {
                "label": "benefits",
                "attributes": [
                    {"label": "Assistência médica", "suid": "X"},
                    {"label": "Vale-transporte", "suid": "Y"},
                ],
            },
            {"label": "remote", "attributes": []},
        ],
    }
    base.update(overrides)
    return base


def test_parse_mosaic_basic():
    spider = IndeedSpider()
    results = [_make_mosaic_result()]
    vagas = spider.parse_mosaic(results)

    assert len(vagas) == 1
    v = vagas[0]
    assert v.title == "Médico Clínico Geral"
    assert v.company == "Hospital São Luiz"
    assert v.location == "São Paulo, SP"
    assert v.source == "indeed"
    assert v.external_id == "abc123def456"
    assert v.url == "https://br.indeed.com/viewjob?jk=abc123def456"


def test_parse_mosaic_salary():
    spider = IndeedSpider()
    results = [_make_mosaic_result()]
    vagas = spider.parse_mosaic(results)

    v = vagas[0]
    assert v.salary == "R$ 15.000 – R$ 30.000 por mês"
    assert v.salary_min == 15000.0
    assert v.salary_max == 30000.0
    assert v.salary_period == "MONTHLY"


def test_parse_mosaic_no_salary():
    spider = IndeedSpider()
    results = [_make_mosaic_result(
        salarySnippet={"currency": "", "salaryTextFormatted": False},
        extractedSalary=None,
    )]
    vagas = spider.parse_mosaic(results)

    v = vagas[0]
    assert v.salary is None
    assert v.salary_min is None
    assert v.salary_max is None


def test_parse_mosaic_job_type():
    spider = IndeedSpider()
    results = [_make_mosaic_result(jobTypes=["Autônomo", "Freelancer"])]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].job_type == "Autônomo, Freelancer"


def test_parse_mosaic_no_job_type():
    spider = IndeedSpider()
    results = [_make_mosaic_result(jobTypes=[])]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].job_type is None


def test_parse_mosaic_benefits():
    spider = IndeedSpider()
    results = [_make_mosaic_result()]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].benefits == ["Assistência médica", "Vale-transporte"]


def test_parse_mosaic_no_benefits():
    spider = IndeedSpider()
    results = [_make_mosaic_result(taxonomyAttributes=[])]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].benefits is None


def test_parse_mosaic_description_from_snippet():
    spider = IndeedSpider()
    results = [_make_mosaic_result(
        snippet="<ul><li>Req 1</li><li>Req 2</li></ul>",
    )]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].description == "Req 1 Req 2"


def test_parse_mosaic_specialty_from_title():
    """normTitle 'Medico' + title has specialty -> extract it."""
    spider = IndeedSpider()
    results = [
        _make_mosaic_result(displayTitle="Médico Cardiologista - Presencial"),
        _make_mosaic_result(displayTitle="Médico Generalista - Florianópolis"),
        _make_mosaic_result(displayTitle="Médico do Trabalho"),
        _make_mosaic_result(displayTitle="Médico"),
    ]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].specialty == "Cardiologista"
    assert vagas[1].specialty == "Generalista"
    assert vagas[2].specialty == "do Trabalho"
    assert vagas[3].specialty is None


def test_parse_mosaic_multiple_results():
    spider = IndeedSpider()
    results = [
        _make_mosaic_result(displayTitle="Médico A", jobkey="aaa"),
        _make_mosaic_result(displayTitle="Médico B", jobkey="bbb"),
    ]
    vagas = spider.parse_mosaic(results)
    assert len(vagas) == 2
    assert vagas[0].external_id == "aaa"
    assert vagas[1].external_id == "bbb"


def test_parse_mosaic_filters_non_medical():
    """Non-medical normTitles should be excluded."""
    spider = IndeedSpider()
    results = [
        _make_mosaic_result(normTitle="Medico", displayTitle="Médico Clínico"),
        _make_mosaic_result(normTitle="Professor De Educação Infantil", displayTitle="Professora Pedagoga"),
        _make_mosaic_result(normTitle="Advogado", displayTitle="Advogado Bancário"),
        _make_mosaic_result(normTitle="Veterinário", displayTitle="Médico Veterinário"),
    ]
    vagas = spider.parse_mosaic(results)
    assert len(vagas) == 1
    assert vagas[0].title == "Médico Clínico"


def test_parse_mosaic_accepts_specialty_normtitles():
    """normTitle with 'Medico' prefix or standalone specialty should be accepted."""
    spider = IndeedSpider()
    results = [
        _make_mosaic_result(normTitle="Médico Cardiologista", displayTitle="Médico Cardiologista", jobkey="k1"),
        _make_mosaic_result(normTitle="Médico Clínico Geral", displayTitle="Médico Clínico Geral", jobkey="k2"),
        _make_mosaic_result(normTitle="Oftalmologista", displayTitle="Médico Oftalmologista", jobkey="k3"),
        _make_mosaic_result(normTitle="Generalista", displayTitle="Médico Generalista", jobkey="k4"),
    ]
    vagas = spider.parse_mosaic(results)
    assert len(vagas) == 4


def test_is_medical_norm():
    """Direct test of the _is_medical_norm filter function."""
    from vagas.spiders.indeed import _is_medical_norm

    # Prefix matches
    assert _is_medical_norm("Medico") is True
    assert _is_medical_norm("Médico Cardiologista") is True
    assert _is_medical_norm("Medico Clínico Geral") is True
    assert _is_medical_norm("medico pediatra") is True

    # Standalone specialties
    assert _is_medical_norm("Oftalmologista") is True
    assert _is_medical_norm("generalista") is True
    assert _is_medical_norm("Geriatra") is True

    # Non-medical
    assert _is_medical_norm("Professor") is False
    assert _is_medical_norm("Advogado") is False
    assert _is_medical_norm("Veterinário") is False
    assert _is_medical_norm("Enfermeiro") is False


def test_parse_mosaic_excludes_non_doctor_titles():
    """Even with medical normTitle, non-doctor display titles are excluded."""
    spider = IndeedSpider()
    results = [
        _make_mosaic_result(normTitle="Medico", displayTitle="Médico Veterinário Cardiologista", jobkey="v1"),
        _make_mosaic_result(normTitle="Generalista", displayTitle="Enfermeiro Generalista", jobkey="v2"),
        _make_mosaic_result(normTitle="Oftalmologista", displayTitle="Auxiliar de Oftalmologia", jobkey="v3"),
        _make_mosaic_result(normTitle="Medico", displayTitle="Conteudista Médico B2C", jobkey="v4"),
        # This one should pass — it's a real doctor
        _make_mosaic_result(normTitle="Medico", displayTitle="Médico Clínico Geral", jobkey="v5"),
    ]
    vagas = spider.parse_mosaic(results)
    assert len(vagas) == 1
    assert vagas[0].external_id == "v5"


def test_parse_mosaic_pubdate():
    """pubDate epoch ms should be parsed into published_at datetime."""
    spider = IndeedSpider()
    # 2026-01-15T12:00:00 UTC in epoch ms
    epoch_ms = 1768507200000
    results = [_make_mosaic_result(pubDate=epoch_ms)]
    vagas = spider.parse_mosaic(results)
    v = vagas[0]
    assert v.published_at is not None
    assert v.published_at.year == 2026
    assert v.published_at.month == 1
    assert v.published_at.day == 15


def test_parse_mosaic_no_pubdate():
    """Missing pubDate should result in published_at = None."""
    spider = IndeedSpider()
    results = [_make_mosaic_result(pubDate=None)]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].published_at is None


def test_parse_mosaic_scoring_defense_in_depth():
    """Defense-in-depth: scoring catches titles that pass normTitle + exclude filters."""
    spider = IndeedSpider()
    results = [
        # Passes _is_medical_norm (normTitle starts with "medico")
        # Passes _TITLE_EXCLUDE_RE (no vet/nurse/etc keywords)
        # But fails scoring: "Closer" as first word + "Clínica Médica" = adjective
        _make_mosaic_result(
            normTitle="Medico",
            displayTitle="Closer - Clínica Médica Estética",
            jobkey="score1",
        ),
        # Real doctor — should pass all filters
        _make_mosaic_result(
            normTitle="Medico",
            displayTitle="Médico Clínico Geral",
            jobkey="score2",
        ),
    ]
    vagas = spider.parse_mosaic(results)
    assert len(vagas) == 1
    assert vagas[0].external_id == "score2"


def test_parse_mosaic_empty():
    spider = IndeedSpider()
    assert spider.parse_mosaic([]) == []
