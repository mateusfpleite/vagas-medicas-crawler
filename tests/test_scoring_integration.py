from vagas.models import Vaga
from vagas.scoring import medical_score, FULL_THRESHOLD


def _make_vaga(title: str, description: str | None = None) -> Vaga:
    return Vaga(title=title, location="Brasil", source="test", url="http://x", description=description)


def test_post_detail_filter_removes_non_doctors():
    """Simulate the cli.py post-detail scoring filter."""
    vagas = [
        _make_vaga("Médico Cardiologista", "CRM ativo, atendimento em hospital."),
        _make_vaga("Secretária Clínica Médica", "Atendimento ao cliente, ensino médio."),
        _make_vaga("Médico do Trabalho", "RQE obrigatório, exames ocupacionais."),
        _make_vaga("PROPAGANDISTA MÉDICO", "Indústria farmacêutica, vendas."),
    ]
    filtered = [v for v in vagas if medical_score(v.title, v.description) >= FULL_THRESHOLD]
    titles = {v.title for v in filtered}
    assert "Médico Cardiologista" in titles
    assert "Médico do Trabalho" in titles
    assert "Secretária Clínica Médica" not in titles
    assert "PROPAGANDISTA MÉDICO" not in titles


def test_post_detail_filter_keeps_ambiguous_with_good_description():
    """Ambiguous title rescued by strong description signals."""
    vaga = _make_vaga("Médico", "Necessário CRM ativo. Plantão 12h na UBS.")
    assert medical_score(vaga.title, vaga.description) >= FULL_THRESHOLD
