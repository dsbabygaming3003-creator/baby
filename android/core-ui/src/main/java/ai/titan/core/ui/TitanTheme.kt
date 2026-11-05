package ai.titan.core.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Graphite = Color(0xFF0B0E13)
val Panel = Color(0xFF11161E)
val Cyan = Color(0xFF82D9F4)
val Muted = Color(0xFF91A0B2)

private val TitanColors = darkColorScheme(
    primary = Cyan,
    onPrimary = Color(0xFF09202A),
    background = Graphite,
    onBackground = Color(0xFFEDF3F8),
    surface = Panel,
    onSurface = Color(0xFFEDF3F8),
    surfaceVariant = Color(0xFF161D27),
    onSurfaceVariant = Muted,
    outline = Color(0xFF263140),
)

@Composable
fun TitanTheme(content: @Composable () -> Unit) {
    isSystemInDarkTheme() // Dark operations theme is intentional in this increment.
    MaterialTheme(colorScheme = TitanColors, content = content)
}
