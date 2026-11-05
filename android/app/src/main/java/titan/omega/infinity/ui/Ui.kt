package titan.omega.infinity.ui

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView

/**
 * TITAN design tokens (see docs/UI_DESIGN_SYSTEM.md).
 *
 * Graphite / deep-dark base, refined blue + cyan accents, elevation by
 * layered surfaces instead of heavy shadows, and glass reserved for the two
 * overlay layers (bottom nav and sheets).
 */
object T {
    const val BG_BASE = 0xFF0B0F14.toInt()
    const val BG_SURFACE = 0xFF121821.toInt()
    const val BG_RAISED = 0xFF18212C.toInt()
    const val BG_OVERLAY = 0xFF1F2A37.toInt()
    const val ACCENT = 0xFF3B82F6.toInt()
    const val CYAN = 0xFF22D3EE.toInt()
    const val SUCCESS = 0xFF34D399.toInt()
    const val WARNING = 0xFFFBBF24.toInt()
    const val DANGER = 0xFFD16287.toInt()
    const val DANGER_STRONG = 0xFFF87171.toInt()
    const val TEXT = 0xFFE6EDF5.toInt()
    const val TEXT_SECONDARY = 0xFF9AA9BC.toInt()
    const val TEXT_DISABLED = 0xFF5C6B7F.toInt()
    const val BORDER = 0xFF223040.toInt()

    const val SPACE_1 = 4
    const val SPACE_2 = 8
    const val SPACE_3 = 12
    const val SPACE_4 = 16
    const val SPACE_5 = 24
    const val SPACE_6 = 32

    const val RADIUS_SM = 8
    const val RADIUS_MD = 14
    const val RADIUS_LG = 22

    const val TYPE_DISPLAY = 28f
    const val TYPE_TITLE = 20f
    const val TYPE_BODY = 15f
    const val TYPE_CAPTION = 12f
}

fun Context.dp(value: Int): Int = TypedValue.applyDimension(
    TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics
).toInt()

fun Context.dpf(value: Float): Float = TypedValue.applyDimension(
    TypedValue.COMPLEX_UNIT_DIP, value, resources.displayMetrics
)

/** Rounded surface used for every card in TITAN. */
fun rounded(color: Int, radiusDp: Int = T.RADIUS_MD, strokeColor: Int? = T.BORDER): GradientDrawable =
    GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        setColor(color)
        cornerRadius = radiusDp.toFloat()
        if (strokeColor != null) setStroke(1, strokeColor)
    }

fun View.setBg(color: Int, radiusDp: Int = T.RADIUS_MD, strokeColor: Int? = T.BORDER) {
    background = rounded(color, radiusDp, strokeColor)
}

fun TextView.style(sizeSp: Float, color: Int, bold: Boolean = false) {
    setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
    setTextColor(color)
    if (bold) setTypeface(typeface, android.graphics.Typeface.BOLD)
}

fun card(context: Context, padding: Int = T.SPACE_4): LinearLayout =
    LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(context.dp(padding), context.dp(padding), context.dp(padding), context.dp(padding))
        setBg(T.BG_SURFACE)
    }

fun heading(context: Context, text: String, size: Float = T.TYPE_TITLE, color: Int = T.TEXT): TextView =
    TextView(context).apply {
        this.text = text
        style(size, color, bold = true)
    }

fun body(context: Context, text: String, color: Int = T.TEXT_SECONDARY, size: Float = T.TYPE_BODY): TextView =
    TextView(context).apply {
        this.text = text
        style(size, color)
        setLineSpacing(2f, 1.05f)
    }

fun caption(context: Context, text: String, color: Int = T.TEXT_SECONDARY): TextView =
    TextView(context).apply {
        this.text = text
        style(T.TYPE_CAPTION, color)
    }

fun primaryButton(context: Context, label: String, onClick: () -> Unit): Button =
    Button(context).apply {
        text = label
        isAllCaps = false
        setTextColor(Color.WHITE)
        background = rounded(T.ACCENT, T.RADIUS_SM, null)
        setOnClickListener { onClick() }
        minHeight = context.dp(46)
    }

fun secondaryButton(context: Context, label: String, onClick: () -> Unit): Button =
    Button(context).apply {
        text = label
        isAllCaps = false
        setTextColor(T.TEXT)
        background = rounded(T.BG_RAISED, T.RADIUS_SM, T.BORDER)
        setOnClickListener { onClick() }
        minHeight = context.dp(42)
    }

fun input(context: Context, hint: String): EditText =
    EditText(context).apply {
        this.hint = hint
        setHintTextColor(T.TEXT_DISABLED)
        setTextColor(T.TEXT)
        setBackground(rounded(T.BG_RAISED, T.RADIUS_SM, T.BORDER))
        setPadding(context.dp(T.SPACE_3), context.dp(T.SPACE_2), context.dp(T.SPACE_3), context.dp(T.SPACE_2))
        textSize = T.TYPE_BODY
    }

fun scrollColumn(context: Context): LinearLayout =
    LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(context.dp(T.SPACE_4), context.dp(T.SPACE_4), context.dp(T.SPACE_4), context.dp(T.SPACE_6))
    }

fun scrollView(context: Context, content: LinearLayout): ScrollView =
    ScrollView(context).apply {
        setBackgroundColor(T.BG_BASE)
        isFillViewport = true
        addView(content)
    }

fun spinner(context: Context): ProgressBar =
    ProgressBar(context).apply {
        isIndeterminate = true
        visibility = View.GONE
    }

fun row(context: Context, vararg children: View): LinearLayout =
    LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        children.forEach { addView(it) }
    }

fun lp(width: Int, height: Int, weight: Float = 0f, marginBottom: Int = 0): LinearLayout.LayoutParams =
    LinearLayout.LayoutParams(
        if (width == ViewGroup.LayoutParams.MATCH_PARENT) ViewGroup.LayoutParams.MATCH_PARENT else width,
        if (height == ViewGroup.LayoutParams.MATCH_PARENT) ViewGroup.LayoutParams.MATCH_PARENT else height,
        weight
    )

/**
 * Deterministic status colour: verified sources are green, pending amber,
 * failures red, and inaccessible sources are explicitly dimmed — colour is
 * never the only signal (an icon/label always accompanies it).
 */
fun statusColor(status: String): Int = when (status.lowercase()) {
    "ok", "verified", "completed", "ready", "active", "succeeded", "published", "available" -> T.SUCCESS
    "empty", "pending", "queued", "running", "tested", "awaiting_approval" -> T.WARNING
    "error", "failed", "rejected", "unauthorized" -> T.DANGER_STRONG
    "inaccessible", "blocked", "unreachable", "degraded" -> T.TEXT_DISABLED
    else -> T.TEXT_SECONDARY
}
