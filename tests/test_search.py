import pytest

from tests.factories import SchemaFactory
from core.models import Schema


@pytest.mark.django_db
def test_stemming_makes_singular_and_plural_equivalent():
    # "Schema" and "Schemas" must return the same result.
    # decoy proves the @@ filter actually excludes non-matches (not just that matches are found).
    schema = SchemaFactory(name="Invoice Schema")
    decoy = SchemaFactory(name="Weather Report")
    for term in ("Schemas", "Schema"):
        results = Schema.objects.public().search(term)
        assert schema in results
        assert decoy not in results


@pytest.mark.django_db
def test_search_is_case_insensitive():
    schema = SchemaFactory(name="Invoice Schema")
    assert schema in Schema.objects.public().search("INVOICE")


@pytest.mark.django_db
def test_search_matches_description_field():
    schema = SchemaFactory(name="ACME Format", description="A standard for invoices")
    assert schema in Schema.objects.public().search("invoice")


@pytest.mark.django_db
def test_name_hit_outranks_description_only_hit():
    # Assert on the rank *values*, not list order.
    # Order under equal ranks is decided by the name tie-break,
    # which would hide a weight bug for some names.
    SchemaFactory(name="Invoice Format", description=None)
    SchemaFactory(name="ACME Format", description="Used for invoice data")
    ranks = {s.name: s.rank for s in Schema.objects.public().search("invoice")}
    assert ranks["Invoice Format"] > ranks["ACME Format"]


@pytest.mark.django_db
def test_blank_query_returns_all_and_preserves_order():
    SchemaFactory(name="One")
    SchemaFactory(name="Two")
    # A blank / None query must neither filter nor reorder: .search() returns the
    # queryset unchanged, so the caller's ordering survives and no relevance
    # ranking is applied. (Whitespace-only counts as blank via .strip().)
    for blank in ("", "   ", None):
        results = Schema.objects.public().order_by("name").search(blank)
        assert [schema.name for schema in results] == ["One", "Two"]


@pytest.mark.django_db
def test_search_excludes_unpublished_schemas():
    SchemaFactory(name="Public Invoice")
    SchemaFactory(name="Private Invoice", published_at=None)
    assert Schema.objects.public().search("invoice").count() == 1


@pytest.mark.django_db
def test_malformed_query_does_not_raise():
    SchemaFactory(name="Invoice")
    # websearch_to_tsquery tolerates junk such as unbalanced quote plus dangling operator.
    # The guarantee is that evaluating the queryset does not raise.
    results = Schema.objects.public().search('"invoice OR -')
    assert results.count() >= 0


@pytest.mark.django_db
def test_generated_vector_is_populated_on_insert():
    # Postgres computes the stored generated column on write
    schema = SchemaFactory(name="Invoice Schema")
    schema.refresh_from_db()
    assert schema.search_vector is not None
