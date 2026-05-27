# Schemas.Pub Manifest Schema

This is a schema for a JSON manifest representing schemas for [Schemas.Pub](https://schemas.pub).

## Properties

A Schemas.Pub manifest is a JSON object with the following properties:

| Name          | Type      | Required | Default | Description                                                                                                                                                             |
| ------------- | --------- | -------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`        | `string`  | Yes      | (none)  | The schema name.                                                                                                                                                        |
| `description` | `string`  | No       | (none)  | A brief description of the schema.                                                                                                                                      |
| `public`      | `boolean` | No       | `false` | Controls whether the schema is publicly hosted on Schemas.Pub. **Note that once public, a schema on Schemas.Pub can't be made private except by a site administrator.** |
| `documents`   | `object`  | Yes      | (none)  | A collection of resources related to the schema, such as definitions, documentation, and implementations.                                                               |

### The `documents` object

The documents object is a key-value collection where each key is a URL, and each value is an object containing metadata about the URL.

Here is an example `documents` object with a schema definition file and its README:

```json
{
  "https://example.com/schema/definition.json": {
    "type": "definition",
    "name": "Schema definition"
  },
  "https://example.com/schema/README.md": {
    "type": "documentation",
    "name": "README",
    "role": "readme",
    "format": "markdown"
  }
}
```

Currently, three types of URLs are supported: definitions, documentation, and implementations.

#### Shared metadata properties

| Name          | Type                                                                               | Required                              | Default | Description                                              |
| ------------- | ---------------------------------------------------------------------------------- | ------------------------------------- | ------- | -------------------------------------------------------- |
| `type`        | `string` (must be one of `"definition"`, `"documentation"`, or `"implementation"`) | Yes                                   | (none)  | The type of resource at the URL this metadata describes. |
| `name`        | `string`                                                                           | Yes for `documentation`, otherwise no | (none)  | A name for the resource.                                 |
| `description` | `string`                                                                           | No                                    | (none)  | A brief description of the URL.                          |

#### Additional `documentation` metadata properties

| Name     | Type                                                                | Required | Default | Description                                                                                             |
| -------- | ------------------------------------------------------------------- | -------- | ------- | ------------------------------------------------------------------------------------------------------- |
| `role`   | `string` (must be one of `"readme"`, `"license"`, `"rfc"`, `"w3c"`) | No       | (none)  | Indicates what kind of documentation the resource is                                                    |
| `format` | `string` (must be one of `"markdown"` or `"plaintext"`)             | No       | (none)  | Indicates the format of the resource content. Markdown and plaintext files are rendered on Schemas.Pub. |

#### Additional `implementation` metadata properties

| Name           | Type      | Required | Default | Description                                     |
| -------------- | --------- | -------- | ------- | ----------------------------------------------- |
| `isOpenSource` | `boolean` | No       | `false` | Indicates if the implementation is open source. |

## Examples

Here's a basic example manifest:

```json
{
  "name": "Phaser Settings",
  "description": "An open-source schema for phaser settings used by Starfleet.",
  "public": true,
  "documents": {
    "https://example.com/schemas/phaser-settings/schema.json": {
      "type": "definition",
      "name": "Schema definition",
      "description": "The JSON Schema specification for phaser settings"
    },
    "https://example.com/schemas/phaser-settings/README.md": {
      "type": "documentation",
      "name": "README",
      "description": "README for the Phaser Settings schema",
      "role": "readme",
      "format": "markdown"
    },
    "https://example.com/schemas/phaser-settings/rfc.txt": {
      "type": "documentation",
      "name": "RFC",
      "description": "The offical RFC for the schema",
      "role": "rfc",
      "format": "plaintext"
    },
    "https://example.com/schemas/phaser-settings/example.json": {
      "type": "documentation",
      "name": "Example",
      "description": "An example of a JSON document using the phaser setting schema"
    },
    "https://example.com/starfleet/enterprise-phaser-settings.json": {
      "type": "implementation",
      "name": "Enterprise D Phaser settings",
      "description": "The Enterprise D's current phaser settings",
      "isOpenSource": true
    }
  }
}
```

Here's a manifest for this schema itself:

```json
{
  "name": "Schemas.Pub Manifest",
  "description": "A manifest representing schemas for Schemas.Pub",
  "public": true,
  "documents": {
    "https://raw.githubusercontent.com/dtinit/schemaindex/refs/heads/main/core/schemas/manifest.schema.json": {
      "type": "definition",
      "name": "Manifest Schema",
      "description": "The definition file for the Manifest Schema"
    },
    "https://raw.githubusercontent.com/dtinit/schemaindex/refs/heads/main/core/schemas/README.md": {
      "type": "documentation",
      "name": "README",
      "description": "The README file for the Manifest Schema",
      "role": "readme",
      "format": "markdown"
    }
  }
}
```
