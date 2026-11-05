# Agent Registry

Seeded version: **1.0.0**. All 20 start `active`; dynamic agents start `draft`.

| # | Agent | Role | Declared tool scopes |
|---|---|---|---|
| 1 | Global Research Agent | research | research.github, knowledge.write |
| 2 | Open-Source Discovery Agent | research | research.github |
| 3 | AI Architecture Agent | architecture | knowledge.read |
| 4 | Senior Coding Agent | coding | project.read/write, test.run |
| 5 | Bug Fixing Agent | coding | project.read/write, test.run |
| 6 | Frontend Development Agent | coding | project.read/write |
| 7 | Android Development Agent | coding | project.read/write, build.run |
| 8 | Backend Development Agent | coding | project.read/write, test.run |
| 9 | API Integration Agent | coding | project.read/write, http.client |
| 10 | Database Engineering Agent | database | project.read, database.migrate |
| 11 | AI Model Specialist | models | model.invoke |
| 12 | Model Evaluation Agent | evaluation | model.invoke, evaluation.write |
| 13 | Multilingual Translation Agent | translation | model.invoke |
| 14 | Voice and Audio Agent | voice | audio.process |
| 15 | Image and Video Agent | media | media.process |
| 16 | Security Engineering Agent | security | project.read, security.scan |
| 17 | Quality Assurance Agent | testing | project.read, test.run |
| 18 | DevOps and Infrastructure Agent | infrastructure | project.read, deployment.request |
| 19 | Build and Release Agent | release | build.run, artifact.read |
| 20 | Documentation Agent | documentation | project.read/write |

Declared permission is not proof that every corresponding tool exists. Current executable tools are listed in `TOOL_REGISTRY.md`; unavailable scopes remain integration boundaries. Runtime registry data comes from `GET /api/v1/agents`, not hardcoded dashboard cards.
