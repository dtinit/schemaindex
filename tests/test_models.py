import pytest

from core.models import Schema, SchemaRef
from factories import UserFactory

@pytest.mark.django_db
def test_multiple_schemarefs():
    # A simple test but leaving it in as I used it to debug a simple thing
    user = UserFactory.create()
    my_schema = Schema.objects.create(name="Star Trek", created_by=user)
    ship_schema = SchemaRef.objects.create(schema=my_schema, url="https://example.com/ships", created_by=user)
    station_schema = SchemaRef.objects.create(schema=my_schema, url="https://example.com/stns", created_by=user)
    assert Schema.objects.all().count() == 1
    assert my_schema.schemaref_set.count() == 2


