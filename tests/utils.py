def assert_schema_matches_manifest(schema, manifest):
    assert schema.name == manifest["name"]
    assert schema.description == manifest.get("description")
    if manifest.get("public"):
        assert schema.published_at is not None
    else:
        assert schema.published_at is None

    manifest_definitions = []
    manifest_documentation = []
    manifest_implementations = []

    for url, metadata in manifest["documents"].items():
        if metadata["type"] == "definition":
            manifest_definitions.append(metadata | {"url": url})
        elif metadata["type"] == "documentation":
            manifest_documentation.append(metadata | {"url": url})
        elif metadata["type"] == "implementation":
            manifest_implementations.append(metadata | {"url": url})

    assert schema.schemaref_set.count() == len(manifest_definitions)
    for definition in manifest_definitions:
        schema_ref = schema.schemaref_set.get(url=definition["url"])
        assert schema_ref.name == definition.get("name")

    assert schema.documentationitem_set.count() == len(manifest_documentation)
    for documentation in manifest_documentation:
        documentation_item = schema.documentationitem_set.get(url=documentation["url"])
        assert documentation_item.name == documentation["name"]
        assert documentation_item.role == documentation.get("role")
        assert documentation_item.format == documentation.get("format")

    assert schema.implementation_set.count() == len(manifest_implementations)
    for implementation in manifest_implementations:
        db_implementation = schema.implementation_set.get(url=implementation["url"])
        # We want to make sure a true value is set,
        # but we treat false and blank as the same.
        if implementation.get("isOpenSource"):
            assert db_implementation.is_open_source
        else:
            assert not db_implementation.is_open_source
