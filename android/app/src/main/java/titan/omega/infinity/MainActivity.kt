package titan.omega.infinity

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import titan.omega.infinity.net.Api
import titan.omega.infinity.screens.AgentsScreen
import titan.omega.infinity.screens.ChatScreen
import titan.omega.infinity.screens.HomeScreen
import titan.omega.infinity.screens.MoreScreen
import titan.omega.infinity.screens.ResearchScreen
import titan.omega.infinity.screens.VoiceScreen
import titan.omega.infinity.screens.WorkspaceScreen
import titan.omega.infinity.ui.T
import titan.omega.infinity.ui.body
import titan.omega.infinity.ui.card
import titan.omega.infinity.ui.caption
import titan.omega.infinity.ui.dp
import titan.omega.infinity.ui.heading
import titan.omega.infinity.ui.input
import titan.omega.infinity.ui.lp
import titan.omega.infinity.ui.primaryButton
import titan.omega.infinity.ui.secondaryButton
import titan.omega.infinity.ui.setBg
import titan.omega.infinity.ui.style

/**
 * TITAN OMEGA INFINITY — single-activity Android client.
 *
 * Navigation: a six-item bottom bar (Home, Chat, Voice, Agents, Workspace,
 * More). Every screen fetches live data from the backend; when the backend is
 * unreachable the screen shows the real error rather than placeholder data.
 */
class MainActivity : Activity() {

    private lateinit var content: FrameLayout
    private lateinit var navBar: LinearLayout
    private val prefs by lazy { getSharedPreferences("titan", Context.MODE_PRIVATE) }
    private var currentTab = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Api.baseUrl = intent?.getStringExtra("base_url") ?: prefs.getString("base_url", null)
            ?: "http://10.0.2.2:8000"
        Api.token = prefs.getString("token", null)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(T.BG_BASE)
        }
        content = FrameLayout(this)
        root.addView(content, lp(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        navBar = buildNavBar()
        root.addView(navBar, lp(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        setContentView(root)

        if (Api.token == null) showAuth() else showTab(currentTab)
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------
    private fun buildNavBar(): LinearLayout {
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(dp(6), dp(6), dp(6), dp(10))
            setBackgroundColor(T.BG_OVERLAY)
        }
        val labels = arrayOf("Home", "Chat", "Voice", "Agents", "Workspace", "More")
        labels.forEachIndexed { index, label ->
            val button = Button(this).apply {
                text = label
                isAllCaps = false
                textSize = 11f
                setTextColor(if (index == currentTab) T.CYAN else T.TEXT_SECONDARY)
                background = android.graphics.drawable.GradientDrawable().apply {
                    shape = android.graphics.drawable.GradientDrawable.RECTANGLE
                    cornerRadius = dp(10).toFloat()
                    setColor(if (index == currentTab) T.BG_RAISED else T.BG_OVERLAY)
                }
                setOnClickListener { showTab(index) }
                layoutParams = lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            }
            bar.addView(button)
        }
        return bar
    }

    private fun showTab(index: Int) {
        currentTab = index
        content.removeAllViews()
        val view: View = when (index) {
            0 -> HomeScreen(this) { showTab(it) }
            1 -> ChatScreen(this)
            2 -> VoiceScreen(this)
            3 -> AgentsScreen(this)
            4 -> WorkspaceScreen(this)
            else -> MoreScreen(this) { showTab(it) }
        }
        content.addView(view, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        refreshNav()
    }

    private fun refreshNav() {
        val bar = navBar
        for (i in 0 until bar.childCount) {
            val button = bar.getChildAt(i) as? Button ?: continue
            button.setTextColor(if (i == currentTab) T.CYAN else T.TEXT_SECONDARY)
            button.background = android.graphics.drawable.GradientDrawable().apply {
                shape = android.graphics.drawable.GradientDrawable.RECTANGLE
                cornerRadius = dp(10).toFloat()
                setColor(if (i == currentTab) T.BG_RAISED else T.BG_OVERLAY)
            }
        }
    }

    // ------------------------------------------------------------------
    // Authentication
    // ------------------------------------------------------------------
    private fun showAuth() {
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(40), dp(24), dp(24))
        }
        column.addView(heading(this, "TITAN OMEGA INFINITY", 26f))
        column.addView(body(this, "V18 · Ultimate Supreme Build — global research, agent orchestration and real tool execution.", T.TEXT_SECONDARY))
        column.addView(space(20))

        val serverInput = input(this, "Backend URL (e.g. http://10.0.2.2:8000)")
        serverInput.setText(Api.baseUrl)
        column.addView(serverInput)
        column.addView(space(12))

        val emailInput = input(this, "Email")
        column.addView(emailInput)
        column.addView(space(8))
        val passwordInput = input(this, "Password (min 8 characters)")
        passwordInput.inputType = android.text.InputType.TYPE_CLASS_TEXT or
            android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        column.addView(passwordInput)
        column.addView(space(16))

        val status = caption(this, "Authenticating against the live backend…")
        column.addView(status)
        column.addView(space(12))

        val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val loginButton = primaryButton(this, "Sign in") {
            authenticate(serverInput.text.toString(), emailInput.text.toString(),
                passwordInput.text.toString(), status, register = false)
        }
        val registerButton = secondaryButton(this, "Create account") {
            authenticate(serverInput.text.toString(), emailInput.text.toString(),
                passwordInput.text.toString(), status, register = true)
        }
        actions.addView(loginButton, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        actions.addView(registerButton, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        column.addView(actions)

        content.removeAllViews()
        content.addView(ScrollView(this).apply {
            setBackgroundColor(T.BG_BASE)
            addView(column)
        })
    }

    private fun authenticate(server: String, email: String, password: String, status: TextView, register: Boolean) {
        if (email.isBlank() || password.length < 8) {
            status.text = "Email is required and the password must be at least 8 characters."
            status.setTextColor(T.DANGER_STRONG)
            return
        }
        Api.baseUrl = server.trimEnd('/')
        status.text = "Contacting ${Api.baseUrl} …"
        status.setTextColor(T.TEXT_SECONDARY)
        Api.run(onSuccess = { response ->
            val token = org.json.JSONObject(response).optString("access_token")
            if (token.isBlank()) {
                status.text = "The server did not return a token."
                status.setTextColor(T.DANGER_STRONG)
            } else {
                Api.token = token
                prefs.edit().putString("token", token).putString("base_url", Api.baseUrl).apply()
                status.text = "Signed in."
                showTab(0)
            }
        }, onError = { error ->
            status.text = "Cannot reach the backend: ${error.message}"
            status.setTextColor(T.DANGER_STRONG)
        }) {
            val payload = org.json.JSONObject()
                .put("email", email)
                .put("password", password)
                .put("display_name", email.substringBefore('@'))
                .put("role", "developer")
                .toString()
            Api.post(if (register) "/api/v1/auth/register" else "/api/v1/auth/login", payload)
        }
    }

    private fun space(dp: Int): View = View(this).apply {
        layoutParams = lp(ViewGroup.LayoutParams.MATCH_PARENT, dp)
    }
}
