package titan.omega.infinity.screens

import android.app.Activity
import android.graphics.Color
import android.view.View
import android.view.ViewGroup
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
import titan.omega.infinity.ui.lp
import titan.omega.infinity.ui.secondaryButton
import titan.omega.infinity.ui.scrollView
import titan.omega.infinity.ui.setBg
import titan.omega.infinity.ui.statusColor
import titan.omega.infinity.ui.style

private fun gap(context: android.content.Context, dp: Int): View =
    View(context).apply { layoutParams = lp(ViewGroup.LayoutParams.MATCH_PARENT, dp) }

/**
 * Home dashboard — bento grid of live operational facts.
 * Nothing here is static: every tile is filled from the running backend.
 */
fun HomeScreen(activity: Activity, navigate: (Int) -> Unit): View {
    val context = activity
    val column = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(context.dp(16), context.dp(20), context.dp(16), context.dp(24))
        setBackgroundColor(T.BG_BASE)
    }

    column.addView(heading(context, "TITAN OMEGA INFINITY", 24f))
    column.addView(caption(context, "V18 · live intelligence status"))
    column.addView(gap(context, 16))

    // --- system health + capabilities (live) -----------------------------
    val healthCard = card(context)
    healthCard.addView(caption(context, "SYSTEM HEALTH"))
    val healthValue = body(context, "contacting backend…")
    healthCard.addView(healthValue)
    column.addView(healthCard)
    column.addView(gap(context, 12))

    val capabilityCard = card(context)
    capabilityCard.addView(caption(context, "CAPABILITY REPORT"))
    val capabilityList = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
    capabilityCard.addView(capabilityList)
    column.addView(capabilityCard)
    column.addView(gap(context, 12))

    // --- quick actions ---------------------------------------------------
    val actions = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
    actions.addView(secondaryButton(context, "Research") { navigate(5) },
        lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
    actions.addView(secondaryButton(context, "Chat") { navigate(1) },
        lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
    column.addView(actions)
    column.addView(gap(context, 16))

    // --- agents ----------------------------------------------------------
    val agentsCard = card(context)
    agentsCard.addView(caption(context, "ACTIVE AGENTS"))
    val agentsValue = body(context, "loading…")
    agentsCard.addView(agentsValue)
    column.addView(agentsCard)
    column.addView(gap(context, 12))

    // --- research activity ----------------------------------------------
    val researchCard = card(context)
    researchCard.addView(caption(context, "RESEARCH ACTIVITY"))
    val researchValue = body(context, "loading…")
    researchCard.addView(researchValue)
    column.addView(researchCard)
    column.addView(gap(context, 12))

    // --- models ----------------------------------------------------------
    val modelsCard = card(context)
    modelsCard.addView(caption(context, "MODEL STATUS"))
    val modelsValue = body(context, "loading…")
    modelsCard.addView(modelsValue)
    column.addView(modelsCard)

    Api.run(onSuccess = { json ->
        val root = JSONObject(json)
        healthValue.text = "${root.optString("status", "?")} · ${root.optString("edition")} · db=${root.optString("database")}"
        healthValue.setTextColor(T.SUCCESS)
    }, onError = { error ->
        healthValue.text = "Backend unreachable: ${error.message}"
        healthValue.setTextColor(T.DANGER_STRONG)
    }) { Api.get("/api/v1/system/health") }

    Api.run(onSuccess = { json ->
        capabilityList.removeAllViews()
        val caps = JSONObject(json).optJSONObject("capabilities") ?: JSONObject()
        val keys = caps.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            val entry = caps.optJSONObject(key) ?: continue
            val status = entry.optString("status", "unknown")
            val line = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
            line.addView(TextView(context).apply {
                text = status.uppercase()
                style(10f, statusColor(status), bold = true)
            }, lp(context.dp(74), ViewGroup.LayoutParams.WRAP_CONTENT))
            line.addView(TextView(context).apply {
                text = key.replace('_', ' ') + " — " + entry.optString("detail", "")
                style(12f, T.TEXT_SECONDARY)
            }, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            capabilityList.addView(line)
        }
    }, onError = { error ->
        capabilityList.removeAllViews()
        capabilityList.addView(body(context, "capabilities unavailable: ${error.message}", T.DANGER_STRONG))
    }) { Api.get("/api/v1/system/capabilities") }

    Api.run(onSuccess = { json ->
        val agents = JSONObject(json).optJSONArray("agents") ?: JSONArray()
        val core = (0 until agents.length()).count { !agents.getJSONObject(it).optBoolean("is_dynamic") }
        agentsValue.text = "$core core agents registered · ${agents.length() - core} dynamic · registry available in the Agents tab"
        agentsValue.setTextColor(T.TEXT)
    }, onError = { error ->
        agentsValue.text = "unavailable: ${error.message}"
        agentsValue.setTextColor(T.DANGER_STRONG)
    }) { Api.get("/api/v1/agents") }

    Api.run(onSuccess = { json ->
        val tasks = JSONObject(json).optJSONArray("tasks") ?: JSONArray()
        if (tasks.length() == 0) {
            researchValue.text = "no research tasks yet — run one from the Research Center"
            researchValue.setTextColor(T.TEXT_SECONDARY)
        } else {
            val latest = tasks.getJSONObject(0)
            researchValue.text = "latest: \"${latest.optString("query").take(70)}\" · ${latest.optString("status")} · ${latest.optInt("findings_count")} findings"
            researchValue.setTextColor(T.TEXT)
        }
    }, onError = { error ->
        researchValue.text = "unavailable: ${error.message}"
        researchValue.setTextColor(T.DANGER_STRONG)
    }) { Api.get("/api/v1/research/tasks") }

    Api.run(onSuccess = { json ->
        val providers = JSONObject(json).optJSONArray("providers") ?: JSONArray()
        val ready = (0 until providers.length()).count { providers.getJSONObject(it).optString("status") == "ready" }
        val noKey = (0 until providers.length()).count { providers.getJSONObject(it).optString("status") == "no_key" }
        modelsValue.text = "${providers.length()} providers · $ready reachable · $noKey without a key"
        modelsValue.setTextColor(if (ready > 0) T.SUCCESS else T.TEXT_SECONDARY)
    }, onError = { error ->
        modelsValue.text = "unavailable: ${error.message}"
        modelsValue.setTextColor(T.DANGER_STRONG)
    }) { Api.get("/api/v1/models/providers") }

    return scrollView(context, column)
}
