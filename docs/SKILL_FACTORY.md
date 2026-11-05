# SKILL FACTORY, MARKETPLACE & LABORATORY

A skill is a versioned, schema'd, permission-scoped, sandbox-tested procedure that an
agent can execute.

---

## 1. Lifecycle

```
draft ──▶ sandbox test ──▶ publish ──▶ install
  │            │
  │            └── fails ──▶ stays a draft (cannot be published)
  └── never publishable without a passing test
```

| Stage | Endpoint | What happens |
|---|---|---|
| draft | `POST /skills` | validates the name, input/output schemas, tool requirements, permission scope and steps; status = `draft` |
| test | `POST /skills/{id}/test` | the skill is executed in the sandbox against its test cases; the result is stored |
| publish | `POST /skills/{id}/publish` | **refused** unless the stored test passed; the quality gate is 0.8 |
| install | `POST /skills/{id}/install` | makes the skill available to agents and workflows |

Verification: AT-28 — a skill is drafted, tested and published through the real endpoints.

---

## 2. Skill contract

| Field | Meaning |
|---|---|
| `id`, `name`, `version` | identity and version |
| `description` | what the skill does |
| `input_schema` / `output_schema` | JSON Schemas — the skill is callable only with a valid payload |
| `tool_requirements` | the tools the skill needs; each is checked before execution |
| `permission_scope` | the scope the skill runs under (`read`, `write`, `network`, `execute`) |
| `steps` | the ordered procedure |
| `test_results` | the recorded sandbox test outcome |
| `status` | `draft` → `tested` → `published` |

---

## 3. Laboratory

The Laboratory is the sandbox where skills are proven:

* the test runs the skill's steps for real inside the sandbox (no network outside the
  allowlist, capped resources);
* every test case is recorded with its expected and actual result;
* the publish gate compares the measured pass ratio against the 0.8 threshold;
* a skill that fails stays a draft and is visible as such in the skill list.

---

## 4. Marketplace

`GET /skills` is the marketplace listing: id, name, version, status, permission scope and
test outcome. Only `published` skills are installable. The Android client shows the same
data in the **More → Skills** tab, so the marketplace in the app is the marketplace on the
server.

---

## 5. Relationship to agents and workflows

* An **agent** may be granted a skill's tools (`tool_permissions`).
* A **workflow** step may invoke a skill by id.
* The **Dynamic Agent Factory** and the **Skill Factory** share the same discipline:
  nothing reaches production without a passing sandbox test.
