package ai.titan.omega

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import ai.titan.core.network.TitanApiFactory
import ai.titan.core.network.TitanRepository
import ai.titan.core.ui.Muted
import ai.titan.core.ui.TitanTheme
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val repository by lazy { TitanRepository(TitanApiFactory.create(BuildConfig.API_BASE_URL)) }
    private val viewModel: TitanViewModel by viewModels { TitanViewModel.Factory(repository) }
    private var speechRecognizer: SpeechRecognizer? = null
    private var textToSpeech: TextToSpeech? = null
    private val voiceTranscript = mutableStateOf("")
    private val voiceStatus = mutableStateOf("Microphone off")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (SpeechRecognizer.isRecognitionAvailable(this)) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).apply {
                setRecognitionListener(voiceListener())
            }
        }
        textToSpeech = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val availability = textToSpeech?.isLanguageAvailable(Locale("bn", "BD"))
                voiceStatus.value = if (availability != null && availability >= TextToSpeech.LANG_AVAILABLE) {
                    "TTS ready; Bengali voice availability reported by device"
                } else {
                    "TTS ready; Bengali voice unavailable on this device"
                }
            }
        }
        setContent {
            TitanTheme {
                val state by viewModel.state.collectAsStateWithLifecycle()
                var route by remember { mutableStateOf("Home") }
                val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
                    voiceStatus.value = if (granted) "Permission granted" else "Microphone permission denied"
                }
                Scaffold(
                    bottomBar = {
                        NavigationBar {
                            listOf("Home", "Chat", "Voice", "Agents", "Research", "More").forEach { item ->
                                NavigationBarItem(
                                    selected = route == item,
                                    onClick = { route = item },
                                    icon = { Text(item.first().toString()) },
                                    label = { Text(item) },
                                )
                            }
                        }
                    },
                ) { padding ->
                    Column(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
                        Text("TITAN Ω", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                        Text(route, color = Muted, modifier = Modifier.padding(bottom = 12.dp))
                        state.error?.let { Text("Error: $it", color = MaterialTheme.colorScheme.error) }
                        when (route) {
                            "Home" -> HomeScreen(state)
                            "Chat" -> ChatScreen(state, viewModel::chat)
                            "Voice" -> VoiceScreen(
                                transcript = voiceTranscript.value,
                                status = voiceStatus.value,
                                onListen = { checkVoicePermission(launcher::launch) },
                                onSpeak = { speak(voiceTranscript.value) },
                                onStop = { stopVoice() },
                            )
                            "Agents" -> AgentsScreen(state)
                            "Research" -> ResearchScreen(state, viewModel::research)
                            else -> MoreScreen()
                        }
                    }
                }
            }
        }
    }

    private fun checkVoicePermission(launch: (String) -> Unit) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startListening()
        } else {
            launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private fun startListening() {
        val recognizer = speechRecognizer
        if (recognizer == null) {
            voiceStatus.value = "Speech recognition unavailable on this device"
            return
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        recognizer.startListening(intent)
        voiceStatus.value = "Listening with visible user consent"
    }

    private fun voiceListener() = object : RecognitionListener {
        override fun onResults(results: Bundle?) {
            voiceTranscript.value = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
            voiceStatus.value = "Recognition complete"
        }
        override fun onPartialResults(results: Bundle?) {
            voiceTranscript.value = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
        }
        override fun onError(error: Int) { voiceStatus.value = "Speech recognition error code: $error" }
        override fun onReadyForSpeech(params: Bundle?) = Unit
        override fun onBeginningOfSpeech() = Unit
        override fun onRmsChanged(rmsdB: Float) { voiceStatus.value = "Live input amplitude: %.1f dB".format(rmsdB) }
        override fun onBufferReceived(buffer: ByteArray?) = Unit
        override fun onEndOfSpeech() { voiceStatus.value = "Speech ended" }
        override fun onEvent(eventType: Int, params: Bundle?) = Unit
    }

    private fun speak(text: String) {
        if (text.isBlank()) {
            voiceStatus.value = "No transcript to speak"
            return
        }
        val locale = if (text.any { it in '\u0980'..'\u09FF' }) Locale("bn", "BD") else Locale.getDefault()
        val result = textToSpeech?.setLanguage(locale)
        if (result == null || result < 0) {
            voiceStatus.value = "Selected voice language unavailable"
            return
        }
        textToSpeech?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "titan-transcript")
    }

    private fun stopVoice() {
        speechRecognizer?.stopListening()
        textToSpeech?.stop()
        voiceStatus.value = "Voice stopped"
    }

    override fun onDestroy() {
        speechRecognizer?.destroy()
        textToSpeech?.shutdown()
        super.onDestroy()
    }
}

@Composable
private fun HomeScreen(state: TitanUiState) {
    if (state.loading) return CircularProgressIndicator()
    val system = state.system
    if (system == null) {
        Text("Backend unavailable. Configure a reachable HTTPS TITAN API.", color = Muted)
        return
    }
    LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(18.dp)) {
            Text("Verified control plane", style = MaterialTheme.typography.titleLarge)
            Text("${system.environment} · ${system.database} · ${system.authentication}", color = Muted)
        } } }
        item { Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Metric("Agents", system.counts.agents, Modifier.weight(1f))
            Metric("Research", system.counts.research_tasks, Modifier.weight(1f))
        } }
        item { Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Metric("Projects", system.counts.projects, Modifier.weight(1f))
            Metric("Runs", system.counts.workflows, Modifier.weight(1f))
        } }
    }
}

@Composable
private fun Metric(label: String, value: Int, modifier: Modifier = Modifier) {
    Card(modifier) { Column(Modifier.padding(16.dp)) { Text(value.toString(), style = MaterialTheme.typography.headlineMedium); Text(label, color = Muted) } }
}

@Composable
private fun ChatScreen(state: TitanUiState, send: (String) -> Unit) {
    var input by remember { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxWidth().height(360.dp)) { item { Text(state.chat.ifBlank { "No messages. Hosted AI requires server credentials; mock output is labeled." }) } }
    OutlinedTextField(input, { input = it }, Modifier.fillMaxWidth(), label = { Text("Message") })
    Spacer(Modifier.height(8.dp))
    Button({ send(input); input = "" }, enabled = !state.working && input.isNotBlank(), modifier = Modifier.fillMaxWidth()) { Text(if (state.working) "Waiting for provider" else "Send") }
}

@Composable
private fun VoiceScreen(transcript: String, status: String, onListen: () -> Unit, onSpeak: () -> Unit, onStop: () -> Unit) {
    Text("Dedicated voice route", style = MaterialTheme.typography.titleLarge)
    Text("Android SpeechRecognizer/TextToSpeech. No hidden recording. Backend ASR/TTS is not implemented.", color = Muted)
    Spacer(Modifier.height(16.dp)); Text(status)
    Spacer(Modifier.height(16.dp)); Text(transcript.ifBlank { "Transcript appears here" })
    Spacer(Modifier.height(16.dp))
    Button(onListen, Modifier.fillMaxWidth()) { Text("Start listening") }
    OutlinedButton(onSpeak, Modifier.fillMaxWidth()) { Text("Speak transcript") }
    OutlinedButton(onStop, Modifier.fillMaxWidth()) { Text("Stop all") }
}

@Composable
private fun AgentsScreen(state: TitanUiState) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(state.agents, key = { it.id }) { agent -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(14.dp)) {
            Text(agent.name, fontWeight = FontWeight.SemiBold)
            Text("${agent.role} · ${agent.status} · v${agent.version}", color = Muted)
        } } }
    }
}

@Composable
private fun ResearchScreen(state: TitanUiState, search: (String) -> Unit) {
    var query by remember { mutableStateOf("") }
    OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth(), label = { Text("GitHub research query") })
    Button({ search(query) }, enabled = !state.working && query.length >= 2, modifier = Modifier.fillMaxWidth()) { Text(if (state.working) "Researching official API" else "Run research") }
    state.research?.let { Card(Modifier.fillMaxWidth().padding(top = 16.dp)) { Column(Modifier.padding(16.dp)) {
        Text("Status: ${it.status}", style = MaterialTheme.typography.titleMedium)
        Text("Task ${it.id}", color = Muted)
        it.error?.let { message -> Text(message) }
    } } }
}

@Composable
private fun MoreScreen() {
    Text("Integration boundaries", style = MaterialTheme.typography.titleLarge)
    Spacer(Modifier.height(10.dp))
    Text("Use the web operations console in this increment for Skills, Workflows, Workspace, Terminal, Model usage and Security audit. Native Android screens for those routes are NOT IMPLEMENTED. No APK build or launch verification has been claimed.", color = Muted)
}
