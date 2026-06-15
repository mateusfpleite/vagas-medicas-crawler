import pytest

from vagas.scoring import medical_score, TITLE_THRESHOLD, FULL_THRESHOLD


class TestTitleScoring:
    """Title-only scoring (pre-detail filter)."""

    @pytest.mark.parametrize("title", [
        "Médico Cardiologista",
        "Médica Pediatra",
        "MÉDICO PLANTONISTA",
        "Médico(a) do Trabalho",
        "Médico Clínico Geral",
        "Médico Ginecologista - APS Santa Marcelina",
        "Médico Cirurgião",
        "Médico Oftalmologista",
        "Médico Endocrinologista",
        "Médica Endocrinologista",
        "Médico do Trabalho RQE",
        "Médico do Trabalho Especialista",
        "Médico do Trabalho Coordenador Nacional com RQE",
        "Médico Psiquiatra",
        "Médico",
    ])
    def test_doctor_titles_score_high(self, title):
        score = medical_score(title)
        assert score >= TITLE_THRESHOLD, (
            f"medical_score({title!r}) = {score}, expected >= {TITLE_THRESHOLD}"
        )

    @pytest.mark.parametrize("title", [
        # "Clínica Médica" as adjective of workplace
        "Consultor Comercial - Clínica Médica Dermatológica",
        "Closer - Clínica Médica Estética",
        "Líder Atendimento Clínica Médica",
        "Secretária Clínica Médica",
        "Supervisora Clínica Médica",
        "Recepcionista Clínica Médica Dermatologia",
        "Secretária Clínica Médica Secretária",
        "Consultor Comercial Clínica Médica",
        # Pharma rep / corporate
        "PROPAGANDISTA MÉDICO JUNIOR",
        "Assessor(a) Médico(a) Prova Funcional",
        # Academic
        "Professor Médico Endocrinologia",
    ])
    def test_non_doctor_titles_score_low(self, title):
        score = medical_score(title)
        assert score < TITLE_THRESHOLD, (
            f"medical_score({title!r}) = {score}, expected < {TITLE_THRESHOLD}"
        )

    def test_empty_title(self):
        assert medical_score("") == 0.0
        assert medical_score("   ") == 0.0


class TestDescriptionScoring:
    """Title + description scoring (post-detail filter)."""

    def test_ambiguous_title_with_crm_scores_high(self):
        """Generic "Médico" title boosted by CRM in description."""
        score = medical_score("Médico", "Necessário CRM ativo e disponibilidade para plantão.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_rqe_scores_high(self):
        score = medical_score("Médico", "Exigido RQE em cardiologia.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_specialty_in_desc(self):
        score = medical_score("Médico", "Buscamos cardiologista para atuar em hospital.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_clinical_procedures(self):
        score = medical_score("Médico", "Atendimento a pacientes, prescrição e diagnóstico.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_healthcare_facility(self):
        score = medical_score("Médico", "Atuar no pronto-socorro do hospital municipal.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_plantao_hours(self):
        score = medical_score("Médico", "Plantão 12h diurno na UTI.")
        assert score >= FULL_THRESHOLD

    def test_sales_description_lowers_score(self):
        """Non-doctor role with sales description."""
        score = medical_score(
            "Consultor Comercial - Clínica Médica",
            "Experiência em vendas e captação de clientes. Metas de venda mensais.",
        )
        assert score < FULL_THRESHOLD

    def test_pharma_industry_lowers_score(self):
        score = medical_score(
            "PROPAGANDISTA MÉDICO JUNIOR",
            "Atuação na indústria farmacêutica. Visitação médica em consultórios.",
        )
        assert score < FULL_THRESHOLD

    def test_low_education_lowers_score(self):
        score = medical_score(
            "Auxiliar de Consultório Médico",
            "Ensino médio completo. Experiência em atendimento ao cliente.",
        )
        assert score < FULL_THRESHOLD

    def test_good_title_reinforced_by_description(self):
        """Strong title + strong description = max score."""
        score = medical_score(
            "Médico Cardiologista",
            "Necessário CRM ativo e RQE. Atendimento em consultório e hospital.",
        )
        assert score == 1.0


def test_veterinary_caught_by_combined_filter():
    """is_medical_title blocks titles that medical_score lets through."""
    from vagas.filters import is_medical_title

    # medical_score alone passes "Médico Veterinário" (0.9 >= 0.5)
    assert medical_score("Médico Veterinário") >= FULL_THRESHOLD
    # But is_medical_title catches it
    assert is_medical_title("Médico Veterinário") is False
