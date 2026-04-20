# Annotating Sessions

Add tags, comments, and ratings to sessions. Annotations make sessions searchable and help your team categorize AI coding work.

## Quick Start: Tagging a Session

```bash
hive tag abc123def456 important
```

That is it. The session now has the tag `important` and can be filtered by it.

## Annotation Types

Hive supports three annotation types:

| Type | Purpose | Example value |
|------|---------|---------------|
| `tag` | Categorize sessions | `important`, `bug-fix`, `needs-review` |
| `comment` | Add free-text notes | `"Good approach to error handling"` |
| `rating` | Rate session quality | `good`, `poor`, `5` |

## CLI: Adding Tags

The `hive tag` command is a shortcut for creating tag annotations:

```bash
# Tag a session
hive tag abc123def456 bug-fix

# Multiple tags (run the command multiple times)
hive tag abc123def456 bug-fix
hive tag abc123def456 needs-review
```

!!! note
    Session IDs support prefix matching. The first 12 characters are usually enough.

## REST API: Full Annotation Support

For comments, ratings, or programmatic access, use the REST API:

=== "Tag"

    ```bash
    curl -X POST http://localhost:3000/api/annotations \
      -H "Content-Type: application/json" \
      -d '{
        "session_id": "abc123def456",
        "type": "tag",
        "value": "important"
      }'
    ```

=== "Comment"

    ```bash
    curl -X POST http://localhost:3000/api/annotations \
      -H "Content-Type: application/json" \
      -d '{
        "session_id": "abc123def456",
        "type": "comment",
        "value": "Clean refactor of the auth module",
        "author": "alice"
      }'
    ```

=== "Rating"

    ```bash
    curl -X POST http://localhost:3000/api/annotations \
      -H "Content-Type: application/json" \
      -d '{
        "session_id": "abc123def456",
        "type": "rating",
        "value": "good",
        "author": "bob"
      }'
    ```

**Response** (all types):

```json
{
  "id": 1,
  "session_id": "abc123def456",
  "type": "tag",
  "value": "important",
  "author": null
}
```

## Searching by Tag

Once sessions are tagged, filter them in the REST API:

```bash
# Find all sessions tagged "important"
curl "http://localhost:3000/api/sessions?tag=important"

# Combine with other filters
curl "http://localhost:3000/api/sessions?tag=bug-fix&author=alice&since=2025-04-01"
```

## Use Cases

### Code Review Workflow

Tag sessions that need review, then query them:

```bash
# Developer tags their session
hive tag abc123def456 needs-review

# Reviewer finds sessions to review
curl "http://localhost:3000/api/sessions?tag=needs-review"

# After review, add a comment and a rating
curl -X POST http://localhost:3000/api/annotations \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123def456", "type": "comment", "value": "Reviewed - looks good", "author": "reviewer"}'

curl -X POST http://localhost:3000/api/annotations \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123def456", "type": "rating", "value": "good", "author": "reviewer"}'
```

### Categorizing by Work Type

Use consistent tag names across the team:

```bash
hive tag <session_id> feature
hive tag <session_id> bug-fix
hive tag <session_id> refactor
hive tag <session_id> docs
hive tag <session_id> test
```

Then generate reports by querying each tag.

### Flagging Quality Issues

Rate sessions to track AI coding quality over time:

```bash
curl -X POST http://localhost:3000/api/annotations \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123def456", "type": "rating", "value": "poor", "author": "alice"}'
```

!!! tip
    View all annotations on a session with `hive show <session_id>`. Annotations appear alongside messages and enrichments.
