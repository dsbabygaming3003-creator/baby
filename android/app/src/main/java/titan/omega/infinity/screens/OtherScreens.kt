package titan.omega.infinity.screens

import android.app.Activity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import titan.omega.infinity.net.Api
import titan.omega.infinity.ui.T
import titan.omega.infinity.ui.body
import titan.omega.infinity.ui.card
import titan.omega.infinity.ui.caption
import titan.omega.infinity.ui.dp
import titan.omega.infinity.ui.heading
import titan.omega.infinity.ui.input
import titan.omega.infinity.ui.lp
import titan.omega.infinity.ui.primaryButton
import titan.omega.infinity.ui.scrollView
import titan.omega.infinity.ui.secondaryButton
import titan.omega.infinity.ui.statusColor
import titan.omega.infinity.ui.style

private fun space(context: android.content.Context, dp: Int): View =
    View(context).apply { layoutParams = lp(ViewGroup.LayoutParams.MATCH_PARENT, dp) }

private fun sectionCard(context: android.content.Context, title: String): Pair<LinearLayout, LinearLayout> {
    val container = card(context)
    container.addView(caption(context, title))
    val inner = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
    container.addView(inner)
    return container to inner
}

/** Agent Center — registry, live run status and the dynamic factory. */
fun AgentsScreen(activity: Activity): View {
    val context = activity
    val column = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(context.dp(16), context.dp(20), context.dp(16), context.dp(24))
        setBackgroundColor(T.BG_BASE)
    }
    column.addView(heading(context, "Agent Center", 22f))
    column.addView(caption(context, "Worker Bossman · 20 specialists + dynamic factory"))
    column.addView(space(context, 12))

    val (registryCard, registryBody) = sectionCard(context, "AGENT REGISTRY")
    column.addView(registryCard)
    column.addView(space(context, 12))

    val (factoryCard, factoryBody) = sectionCard(context, "DYNAMIC AGENT FACTORY")
    val nameInput = input(context, "New agent name")
    factoryBody.addView(nameInput)
    factoryBody.addView(space(context, 8))
    val roleInput = input(context, "Role (e.g. performance optimisation)")
    factoryBody.addView(roleInput)
    factoryBody.addView(space(context, 8))

    fun showDetail(agent: JSONObject) {
        android.app.AlertDialog.Builder(context)
            .setTitle(agent.optString("name"))
            .setMessage(
                "id: " + agent.optString("id") + "\n" +
                    "role: " + agent.optString("role") + "\n" +
                    "description: " + agent.optString("description") + "\n\n" +
                    "tools: " + (agent.optJSONArray("tool_permissions") ?: JSONArray()).toString() + "\n" +
                    "memory scope: " + agent.optString("memory_scope") + "\n" +
                    "model: " + (agent.optJSONObject("model") ?: JSONObject()).toString())
            .setPositiveButton("Close", null)
            .show()
    }

    fun loadRegistry() {
        Api.run(onSuccess = { json ->
            val agents = JSONObject(json).optJSONArray("agents") ?: JSONArray()
            registryBody.removeAllViews()
            for (i in 0 until agents.length()) {
                val agent = agents.getJSONObject(i)
                val row = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
                row.addView(TextView(context).apply {
                    text = agent.optString("name")
                    style(14f, T.TEXT, bold = true)
                })
                val status = agent.optString("status")
                row.addView(TextView(context).apply {
                    text = agent.optString("role") + " · " + status + " · quality " +
                        agent.optDouble("quality_score") + if (agent.optBoolean("is_dynamic")) " · dynamic" else ""
                    style(12f, statusColor(status))
                })
                row.setOnClickListener { showDetail(agent) }
                registryBody.addView(row)
                registryBody.addView(space(context, 8))
            }
        }, onError = { error ->
            registryBody.removeAllViews()
            registryBody.addView(body(context, "registry unavailable: " + error.message, T.DANGER_STRONG))
        }) { Api.get("/api/v1/agents") }
    }

    val factoryButton = primaryButton(context, "Create agent") {
        factoryBody.addView(body(context, "creating…"))
        Api.run(onSuccess = { json ->
            val result = JSONObject(json)
            factoryBody.addView(body(context,
                "created " + result.optString("agent_id") + " · status " + result.optString("status") + "\n" +
                    result.optString("message")))
            loadRegistry()
        }, onError = { error ->
            factoryBody.addView(body(context, "failed: " + error.message, T.DANGER_STRONG))
        }) {
            Api.post("/api/v1/agents/factory", JSONObject()
                .put("name", nameInput.text.toString())
                .put("role", roleInput.text.toString())
                .put("specification", "Specialised agent created from the Android client")
                .toString())
        }
    }
    factoryBody.addView(factoryButton)
    column.addView(factoryCard)
    column.addView(space(context, 12))

    loadRegistry()
    return scrollView(context, column)
}

/** Research Center — live task execution with per-connector status. */
fun ResearchScreen(activity: Activity): View {
    val context = activity
    val column = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(context.dp(16), context.dp(20), context.dp(16), context.dp(24))
        setBackgroundColor(T.BG_BASE)
    }
    column.addView(heading(context, "Research Center", 22f))
    column.addView(caption(context, "global multi-platform discovery with source verification"))
    column.addView(space(context, 12))

    val queryInput = input(context, "Research query")
    column.addView(queryInput)
    column.addView(space(context, 8))

    val selected = mutableSetOf("github")
    val platformRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
    val platforms = arrayOf("github", "npm", "pypi", "arxiv", "reddit", "huggingface")
    platforms.forEach { name ->
        lateinit var chip: Button
        chip = secondaryButton(context, name) {
            if (selected.contains(name)) selected.remove(name) else selected.add(name)
            chip.setTextColor(if (selected.contains(name)) T.CYAN else T.TEXT_SECONDARY)
        }
        platformRow.addView(chip, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
    }
    column.addView(platformRow)
    column.addView(space(context, 10))

    val (connectorCard, connectorBody) = sectionCard(context, "CONNECTOR REACHABILITY")
    column.addView(connectorCard)
    column.addView(space(context, 12))

    val (resultCard, resultBody) = sectionCard(context, "LATEST RESULT")
    column.addView(resultCard)
    column.addView(space(context, 12))

    val (historyCard, historyBody) = sectionCard(context, "RESEARCH HISTORY")
    column.addView(historyCard)

    fun renderResult(json: String) {
        val result = JSONObject(json)
        resultBody.removeAllViews()
        resultBody.addView(body(context,
            "status " + result.optString("status") + " · " + result.optInt("documents") + " documents · " +
                result.optInt("findings") + " findings · " + result.optInt("verified_documents") + " verified"))
        resultBody.addView(space(context, 8))
        val connectors = result.optJSONArray("connectors") ?: JSONArray()
        for (i in 0 until connectors.length()) {
            val connector = connectors.getJSONObject(i)
            val status = connector.optString("status")
            val detail = connector.optString("detail")
            resultBody.addView(TextView(context).apply {
                text = connector.optString("connector_id") + " — " + status +
                    if (detail.isNotBlank()) " · " + detail.take(70) else ""
                style(12f, statusColor(status))
            })
        }
        val report = result.optString("report_path")
        if (report.isNotBlank()) {
            resultBody.addView(space(context, 6))
            resultBody.addView(caption(context, "report: " + report))
        }
    }

    lateinit var runButton: Button
    runButton = primaryButton(context, "Run research") {
        runButton.isEnabled = false
        runButton.text = "running…"
        Api.run(onSuccess = { created ->
            val taskId = JSONObject(created).optString("task_id")
            Api.run(onSuccess = { resultJson ->
                runButton.isEnabled = true
                runButton.text = "Run research"
                renderResult(resultJson)
            }, onError = { error ->
                runButton.isEnabled = true
                runButton.text = "Run research"
                resultBody.addView(body(context, "task failed: " + error.message, T.DANGER_STRONG))
            }) { Api.post("/api/v1/research/tasks/" + taskId + "/run", "{}") }
        }, onError = { error ->
            runButton.isEnabled = true
            runButton.text = "Run research"
            resultBody.addView(body(context, "could not start task: " + error.message, T.DANGER_STRONG))
        }) {
            Api.post("/api/v1/research/tasks", JSONObject()
                .put("query", queryInput.text.toString())
                .put("platforms", JSONArray(selected.toList()))
                .toString())
        }
    }
    column.addView(runButton)
    column.addView(space(context, 12))

    Api.run(onSuccess = { json ->
        connectorBody.removeAllViews()
        val results = JSONObject(json).optJSONArray("results") ?: JSONArray()
        for (i in 0 until results.length()) {
            val entry = results.getJSONObject(i)
            val status = entry.optString("status")
            connectorBody.addView(TextView(context).apply {
                text = entry.optString("connector_id") + " — " + status +
                    " (" + entry.optDouble("latency_ms") + "ms)"
                style(12f, statusColor(status))
            })
        }
    }, onError = { error ->
        connectorBody.addView(body(context, "probe failed: " + error.message, T.DANGER_STRONG))
    }) { Api.get("/api/v1/research/connectors/probe") }

    Api.run(onSuccess = { json ->
        historyBody.removeAllViews()
        val tasks = JSONObject(json).optJSONArray("tasks") ?: JSONArray()
        if (tasks.length() == 0) historyBody.addView(body(context, "no research history yet"))
        for (i in 0 until tasks.length()) {
            val task = tasks.getJSONObject(i)
            val status = task.optString("status")
            historyBody.addView(TextView(context).apply {
                text = task.optString("query").take(48) + " — " + status + " · " +
                    task.optInt("findings_count") + " findings"
                style(12f, statusColor(status))
            })
        }
    }, onError = { error ->
        historyBody.addView(body(context, "history unavailable: " + error.message, T.DANGER_STRONG))
    }) { Api.get("/api/v1/research/tasks") }

    return scrollView(context, column)
}

/** Workspace — projects, files and a real terminal. */
fun WorkspaceScreen(activity: Activity): View {
    val context = activity
    val column = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(context.dp(16), context.dp(20), context.dp(16), context.dp(24))
        setBackgroundColor(T.BG_BASE)
    }
    column.addView(heading(context, "Workspace", 22f))
    column.addView(caption(context, "projects · files · real sandboxed terminal"))
    column.addView(space(context, 12))

    val (projectCard, projectBody) = sectionCard(context, "PROJECTS")
    column.addView(projectCard)
    column.addView(space(context, 12))

    val (terminalCard, terminalBody) = sectionCard(context, "TERMINAL")
    val commandInput = input(context, "Command (allowlisted)")
    terminalBody.addView(commandInput)
    terminalBody.addView(space(context, 8))
    val output = body(context, "no output yet")

    lateinit var runButton: Button
    runButton = primaryButton(context, "Run") {
        runButton.isEnabled = false
        Api.run(onSuccess = { json ->
            runButton.isEnabled = true
            val result = JSONObject(json)
            val ok = result.optBoolean("ok", false)
            output.text = buildString {
                append("$ " + commandInput.text.toString() + "\n")
                append(result.optString("stdout"))
                if (result.optString("stderr").isNotBlank()) append("\n[stderr] " + result.optString("stderr"))
                append("\nexit=" + result.optString("exit_code") + " · " + result.optString("error_message"))
            }
            output.setTextColor(if (ok) T.TEXT else T.DANGER_STRONG)
        }, onError = { error ->
            runButton.isEnabled = true
            output.text = "error: " + error.message
            output.setTextColor(T.DANGER_STRONG)
        }) {
            Api.post("/api/v1/terminal/exec",
                JSONObject().put("command", commandInput.text.toString()).toString())
        }
    }
    terminalBody.addView(runButton)
    terminalBody.addView(space(context, 8))
    terminalBody.addView(output)
    column.addView(terminalCard)
    column.addView(space(context, 12))

    val (buildCard, buildBody) = sectionCard(context, "BUILD CENTER")
    column.addView(buildCard)

    Api.run(onSuccess = { json ->
        projectBody.removeAllViews()
        val projects = JSONObject(json).optJSONArray("projects") ?: JSONArray()
        if (projects.length() == 0) projectBody.addView(body(context, "no projects yet"))
        for (i in 0 until projects.length()) {
            val project = projects.getJSONObject(i)
            projectBody.addView(TextView(context).apply {
                text = project.optString("name") + " · " + project.optString("language") + " · " +
                    project.optString("status")
                style(13f, T.TEXT)
            })
        }
    }, onError = { error ->
        projectBody.addView(body(context, "projects unavailable: " + error.message, T.DANGER_STRONG))
    }) { Api.get("/api/v1/projects") }

    Api.run(onSuccess = { json ->
        buildBody.removeAllViews()
        val builds = JSONObject(json).optJSONArray("builds") ?: JSONArray()
        if (builds.length() == 0) buildBody.addView(body(context, "no builds recorded"))
        for (i in 0 until builds.length()) {
            val build = builds.getJSONObject(i)
            val status = build.optString("status")
            buildBody.addView(TextView(context).apply {
                text = build.optString("name") + " — " + status + " · exit " + build.optString("exit_code")
                style(12f, statusColor(status))
            })
        }
    }, onError = { error ->
        buildBody.addView(body(context, "builds unavailable: " + error.message, T.DANGER_STRONG))
    }) { Api.get("/api/v1/builds") }

    return scrollView(context, column)
}

/** More — models, skills, workflows, memory and security. */
fun MoreScreen(activity: Activity, navigate: (Int) -> Unit): View {
    val context = activity
    val root = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setBackgroundColor(T.BG_BASE)
    }
    val container = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(context.dp(16), context.dp(20), context.dp(16), context.dp(24))
    }
    val scroller = android.widget.ScrollView(context).apply {
        setBackgroundColor(T.BG_BASE)
        addView(container)
    }
    root.addView(scroller, lp(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

    var current = "models"

    fun renderModels(target: LinearLayout) {
        val (modelCard, modelBody) = sectionCard(context, "MODEL REGISTRY")
        target.addView(modelCard)
        Api.run(onSuccess = { json ->
            modelBody.removeAllViews()
            val models = JSONObject(json).optJSONArray("models") ?: JSONArray()
            for (i in 0 until models.length()) {
                val model = models.getJSONObject(i)
                val verified = model.optBoolean("verified_identifier")
                modelBody.addView(TextView(context).apply {
                    text = model.optString("id") + " · " + model.optString("provider_id") +
                        if (verified) " ✓" else ""
                    style(12f, if (verified) T.TEXT else T.TEXT_SECONDARY)
                })
            }
        }, onError = { modelBody.addView(body(context, "unavailable: " + it.message, T.DANGER_STRONG)) }) {
            Api.get("/api/v1/models")
        }
        target.addView(space(context, 12))
        val (providerCard, providerBody) = sectionCard(context, "PROVIDER STATUS")
        target.addView(providerCard)
        Api.run(onSuccess = { json ->
            providerBody.removeAllViews()
            val providers = JSONObject(json).optJSONArray("providers") ?: JSONArray()
            for (i in 0 until providers.length()) {
                val provider = providers.getJSONObject(i)
                val status = provider.optString("status")
                providerBody.addView(TextView(context).apply {
                    text = provider.optString("provider") + " — " + status + " · " +
                        provider.optString("detail").take(60)
                    style(12f, statusColor(status))
                })
            }
        }, onError = { providerBody.addView(body(context, "unavailable: " + it.message, T.DANGER_STRONG)) }) {
            Api.get("/api/v1/models/providers")
        }
    }

    fun renderSkills(target: LinearLayout) {
        val (skillCard, skillBody) = sectionCard(context, "SKILL MARKETPLACE")
        target.addView(skillCard)
        Api.run(onSuccess = { json ->
            skillBody.removeAllViews()
            val skills = JSONObject(json).optJSONArray("skills") ?: JSONArray()
            if (skills.length() == 0) {
                skillBody.addView(body(context, "no skills yet — create one from the Agent Center"))
            }
            for (i in 0 until skills.length()) {
                val skill = skills.getJSONObject(i)
                val status = skill.optString("status")
                skillBody.addView(TextView(context).apply {
                    text = skill.optString("name") + " v" + skill.optString("version") + " — " + status +
                        " · quality " + skill.optDouble("quality_score")
                    style(12f, statusColor(status))
                })
            }
        }, onError = { skillBody.addView(body(context, "unavailable: " + it.message, T.DANGER_STRONG)) }) {
            Api.get("/api/v1/skills")
        }
    }

    fun renderWorkflows(target: LinearLayout) {
        val (workflowCard, workflowBody) = sectionCard(context, "WORKFLOWS")
        target.addView(workflowCard)
        target.addView(space(context, 12))
        val (runCard, runBody) = sectionCard(context, "WORKFLOW RUNS")
        target.addView(runCard)
        Api.run(onSuccess = { json ->
            workflowBody.removeAllViews()
            val workflows = JSONObject(json).optJSONArray("workflows") ?: JSONArray()
            if (workflows.length() == 0) workflowBody.addView(body(context, "no workflows defined"))
            for (i in 0 until workflows.length()) {
                val workflow = workflows.getJSONObject(i)
                workflowBody.addView(TextView(context).apply {
                    text = workflow.optString("name") + " · " + workflow.optString("status")
                    style(13f, T.TEXT)
                })
            }
        }, onError = { workflowBody.addView(body(context, "unavailable: " + it.message, T.DANGER_STRONG)) }) {
            Api.get("/api/v1/workflows")
        }
        Api.run(onSuccess = { json ->
            runBody.removeAllViews()
            val runs = JSONObject(json).optJSONArray("runs") ?: JSONArray()
            if (runs.length() == 0) runBody.addView(body(context, "no runs yet"))
            for (i in 0 until runs.length()) {
                val run = runs.getJSONObject(i)
                val status = run.optString("status")
                val completed = run.optJSONArray("completed_steps")
                runBody.addView(TextView(context).apply {
                    text = run.optString("workflow_id").take(12) + " — " + status +
                        " · steps " + (completed?.length() ?: 0)
                    style(12f, statusColor(status))
                })
            }
        }, onError = { runBody.addView(body(context, "unavailable: " + it.message, T.DANGER_STRONG)) }) {
            Api.get("/api/v1/workflows/runs")
        }
    }

    fun renderMemory(target: LinearLayout) {
        val (memoryCard, memoryBody) = sectionCard(context, "MEMORY")
        target.addView(memoryCard)
        Api.run(onSuccess = { json ->
            memoryBody.removeAllViews()
            val entries = JSONObject(json).optJSONArray("entries") ?: JSONArray()
            if (entries.length() == 0) memoryBody.addView(body(context, "no memory entries"))
            for (i in 0 until entries.length()) {
                val entry = entries.getJSONObject(i)
                memoryBody.addView(TextView(context).apply {
                    text = "[" + entry.optString("scope") + "] " + entry.optString("content").take(70)
                    style(12f, T.TEXT)
                })
            }
        }, onError = { memoryBody.addView(body(context, "unavailable: " + it.message, T.DANGER_STRONG)) }) {
            Api.get("/api/v1/memory")
        }
    }

    fun renderSecurity(target: LinearLayout) {
        val (securityCard, securityBody) = sectionCard(context, "SECURITY CENTER")
        target.addView(securityCard)
        Api.run(onSuccess = { json ->
            securityBody.removeAllViews()
            val summary = JSONObject(json)
            securityBody.addView(body(context, "role: " + summary.optString("current_role")))
            securityBody.addView(body(context, "scopes: " +
                (summary.optJSONArray("scopes") ?: JSONArray()).toString()))
            securityBody.addView(body(context, "tools: " + summary.optInt("tool_count") +
                " · sandbox: " + summary.optString("sandbox_backend")))
            val limits = summary.optJSONObject("sandbox_limits")
            if (limits != null) {
                securityBody.addView(body(context,
                    "limits: cpu " + limits.optInt("cpu_seconds") + "s · mem " + limits.optInt("memory_mb") +
                        "MB · procs " + limits.optInt("max_processes") + " · timeout " +
                        limits.optInt("timeout_seconds") + "s"))
            }
            securityBody.addView(body(context, summary.optString("note")))
        }, onError = { securityBody.addView(body(context, "unavailable: " + it.message, T.DANGER_STRONG)) }) {
            Api.get("/api/v1/security/summary")
        }
    }

    fun render() {
        container.removeAllViews()
        container.addView(heading(context, "More", 22f))
        container.addView(caption(context, "models · skills · workflows · memory · security"))
        container.addView(space(context, 12))

        val tabs = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        val names = listOf("models", "skills", "workflows", "memory", "security")
        names.forEach { name ->
            val chip = secondaryButton(context, name) {
                current = name
                render()
            }
            chip.setTextColor(if (name == current) T.CYAN else T.TEXT_SECONDARY)
            tabs.addView(chip, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        container.addView(tabs)
        container.addView(space(context, 12))

        when (current) {
            "models" -> renderModels(container)
            "skills" -> renderSkills(container)
            "workflows" -> renderWorkflows(container)
            "memory" -> renderMemory(container)
            else -> renderSecurity(container)
        }
    }

    render()
    return root
}
