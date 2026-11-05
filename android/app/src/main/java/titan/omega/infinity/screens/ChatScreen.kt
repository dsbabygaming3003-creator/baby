package titan.omega.infinity.screens

import android.app.Activity
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.ScrollView
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
import titan.omega.infinity.ui.setBg
import titan.omega.infinity.ui.style

/**
 * Dedicated Chat Studio.
 *
 * Messages stream from the server over SSE; the transcript is persisted
 * server-side, so the list survives a restart.
 */
fun ChatScreen(activity: Activity): View {
    val context = activity
    val root = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setBackgroundColor(T.BG_BASE)
    }

    val listContainer = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(context.dp(16), 0, context.dp(16), context.dp(12))
    }
    val scroller = ScrollView(context).apply {
        setBackgroundColor(T.BG_BASE)
        addView(listContainer)
    }
    root.addView(scroller, lp(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

    val composer = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.BOTTOM
        setPadding(context.dp(12), context.dp(8), context.dp(12), context.dp(10))
        setBackgroundColor(T.BG_OVERLAY)
    }
    val messageInput = input(context, "Message TITAN… (Bengali supported)")
    composer.addView(messageInput, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
    root.addView(composer)

    var conversationId: String? = null
    val statusLine = caption(context, "connecting…")

    fun addBubble(role: String, text: String, color: Int, assistant: Boolean): TextView {
        val bubble = card(context).apply { setBg(color, 14) }
        bubble.addView(caption(context, role, if (assistant) T.CYAN else T.TEXT))
        val message = body(context, text, T.TEXT)
        bubble.addView(message)
        listContainer.addView(bubble, lp(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        listContainer.addView(View(context).apply {
            layoutParams = lp(ViewGroup.LayoutParams.MATCH_PARENT, context.dp(8))
        })
        scroller.post { scroller.fullScroll(View.FOCUS_DOWN) }
        return message
    }

    fun updateBubble(target: TextView, text: String, append: Boolean) {
        target.text = if (append) target.text.toString() + text else text
    }

    fun startConversation() {
        Api.run(onSuccess = { json ->
            conversationId = JSONObject(json).optString("id")
            listContainer.removeAllViews()
            listContainer.addView(statusLine)
        }, onError = { error ->
            statusLine.text = "cannot create conversation: ${error.message}"
            statusLine.setTextColor(T.DANGER_STRONG)
        }) { Api.post("/api/v1/chat/conversations", JSONObject().put("title", "TITAN session").toString()) }
    }

    fun send() {
        val text = messageInput.text.toString().trim()
        if (text.isEmpty()) return
        messageInput.setText("")
        addBubble("You", text, T.ACCENT, false)
        val pending = addBubble("TITAN", "…", T.BG_RAISED, false)
        val id = conversationId
        if (id.isNullOrBlank()) {
            startConversation()
            return
        }
        Api.streamSse(
            "/api/v1/chat/stream?q=" + java.net.URLEncoder.encode(text, "UTF-8") +
                "&conversation_id=$id",
            onDelta = { delta -> updateBubble(pending, delta, append = true) },
            onDone = { meta ->
                val info = runCatching { JSONObject(meta) }.getOrNull()
                updateBubble(pending, "\n\n— " + (info?.optString("model") ?: "?") + " · " +
                    (info?.optInt("tokens_out") ?: 0) + " tokens", append = true)
            },
            onError = { error ->
                updateBubble(pending, "\n[stream error] " + error.message, append = true)
            })
    }

    val header = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(context.dp(16), context.dp(14), context.dp(16), context.dp(10))
    }
    header.addView(heading(context, "Chat Studio", 20f), lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
    val newChat = TextView(context).apply {
        text = "New chat"
        style(13f, T.CYAN)
        setPadding(context.dp(10), context.dp(8), context.dp(10), context.dp(8))
        setOnClickListener { startConversation() }
    }
    header.addView(newChat)
    root.addView(header, 0)

    val sendButton = primaryButton(context, "Send") { send() }
    composer.addView(sendButton, lp(context.dp(92), ViewGroup.LayoutParams.WRAP_CONTENT))

    // Load history for the most recent conversation, if any.
    Api.run(onSuccess = { json ->
        val conversations = JSONObject(json).optJSONArray("conversations") ?: JSONArray()
        if (conversations.length() == 0) {
            statusLine.text = "No conversation yet — send a message to begin."
            listContainer.addView(statusLine)
            startConversation()
            return@run
        }
        val latest = conversations.getJSONObject(0)
        conversationId = latest.optString("id")
        statusLine.text = "conversation: " + latest.optString("title") +
            " (" + latest.optInt("message_count") + " messages)"
        listContainer.addView(statusLine)
        val targetId = conversationId
        Api.run(onSuccess = { messagesJson ->
            val messages = JSONObject(messagesJson).optJSONArray("messages") ?: JSONArray()
            listContainer.removeAllViews()
            for (i in 0 until messages.length()) {
                val message = messages.getJSONObject(i)
                val role = message.optString("role")
                addBubble(if (role == "user") "You" else "TITAN", message.optString("content"),
                    if (role == "user") T.ACCENT else T.BG_RAISED, role != "user")
            }
        }, onError = { error ->
            listContainer.addView(body(context, "history unavailable: " + error.message, T.DANGER_STRONG))
        }) { Api.get("/api/v1/chat/conversations/$targetId/messages") }
    }, onError = { error ->
        statusLine.text = "backend unreachable: " + error.message
        statusLine.setTextColor(T.DANGER_STRONG)
        listContainer.addView(statusLine)
    }) { Api.get("/api/v1/chat/conversations") }

    return root
}
