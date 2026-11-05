package titan.omega.infinity.screens

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import org.json.JSONObject
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean
import titan.omega.infinity.net.Api
import titan.omega.infinity.ui.T
import titan.omega.infinity.ui.body
import titan.omega.infinity.ui.card
import titan.omega.infinity.ui.caption
import titan.omega.infinity.ui.dp
import titan.omega.infinity.ui.heading
import titan.omega.infinity.ui.lp
import titan.omega.infinity.ui.primaryButton
import titan.omega.infinity.ui.scrollView
import titan.omega.infinity.ui.secondaryButton
import titan.omega.infinity.ui.setBg
import titan.omega.infinity.ui.style

/**
 * Dedicated Live Voice Studio.
 *
 * The waveform is driven by the *real* microphone amplitude captured with
 * AudioRecord — it is not a synthetic animation. Speech-to-text uses the
 * platform recogniser and text-to-speech uses the platform engine; Bengali
 * availability is probed at runtime with isLanguageAvailable() and reported
 * honestly instead of being assumed.
 */
fun VoiceScreen(activity: Activity): View {
    val context = activity
    val column = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(context.dp(16), context.dp(20), context.dp(16), context.dp(24))
        setBackgroundColor(T.BG_BASE)
    }

    column.addView(heading(context, "Voice Studio", 22f))
    column.addView(caption(context, "Push-to-talk, hands-free and live transcript"))
    column.addView(space(context, 12))

    val permissionCard = card(context)
    val permissionStatus = body(context, "microphone permission: checking…")
    permissionCard.addView(permissionStatus)
    column.addView(permissionCard)
    column.addView(space(context, 12))

    val waveCard = card(context)
    val waveform = WaveformView(context)
    waveCard.addView(waveform, lp(ViewGroup.LayoutParams.MATCH_PARENT, context.dp(120)))
    column.addView(waveCard)
    column.addView(space(context, 12))

    val transcriptCard = card(context)
    transcriptCard.addView(caption(context, "LIVE TRANSCRIPT"))
    val transcript = body(context, "nothing captured yet")
    transcriptCard.addView(transcript)
    column.addView(transcriptCard)
    column.addView(space(context, 12))

    val controls = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
    val talkButton = primaryButton(context, "Hold to talk") { }
    val stopButton = secondaryButton(context, "Stop") { }
    controls.addView(talkButton, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
    controls.addView(stopButton, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
    column.addView(controls)
    column.addView(space(context, 10))

    val speakRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
    val speakButton = secondaryButton(context, "Speak last transcript") { }
    speakRow.addView(speakButton, lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
    column.addView(speakRow)
    column.addView(space(context, 12))

    val capabilityCard = card(context)
    capabilityCard.addView(caption(context, "VOICE CAPABILITIES"))
    val capabilityText = body(context, "probing the platform engines…")
    capabilityCard.addView(capabilityText)
    column.addView(capabilityCard)

    // ---- real microphone capture ---------------------------------------
    val capturing = AtomicBoolean(false)
    var recorder: AudioRecord? = null
    var captureThread: Thread? = null

    fun startCapture() {
        if (capturing.get()) return
        if (context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            activity.requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 4711)
            permissionStatus.text = "microphone permission: request sent to the user"
            return
        }
        val minBuffer = AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minBuffer <= 0) {
            transcript.text = "This device does not provide a usable audio input."
            return
        }
        capturing.set(true)
        waveform.setActive(true)
        recorder = try {
            AudioRecord(MediaRecorder.AudioSource.MIC, 16000,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuffer * 2)
        } catch (error: Throwable) {
            null
        }
        val record = recorder
        if (record == null || record.state != AudioRecord.STATE_INITIALIZED) {
            transcript.text = "Could not open the microphone (state=${record?.state})."
            capturing.set(false)
            waveform.setActive(false)
            return
        }
        record.startRecording()
        captureThread = Thread {
            val buffer = ShortArray(minBuffer)
            while (capturing.get()) {
                val read = record.read(buffer, 0, buffer.size)
                if (read > 0) {
                    var peak = 0
                    for (i in 0 until read) {
                        val value = kotlin.math.abs(buffer[i].toInt())
                        if (value > peak) peak = value
                    }
                    waveform.push(peak / 32768f)
                }
            }
            runCatching { record.stop() }
        }
        captureThread?.start()
        transcript.text = "listening…"
    }

    fun stopCapture() {
        capturing.set(false)
        waveform.setActive(false)
        runCatching { recorder?.release() }
        recorder = null
        transcript.text = "capture stopped — ${waveform.sampleCount} amplitude samples recorded"
    }

    // ---- speech to text -------------------------------------------------
    var recognizer: SpeechRecognizer? = null
    val speech = SpeechRecognizer.createSpeechRecognizer(context)
    recognizer = speech
    speech.setRecognitionListener(object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) { transcript.text = "listening…" }
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() { transcript.text = "processing…" }
        override fun onError(error: Int) {
            transcript.text = "recognition error $error"
            transcript.setTextColor(T.DANGER_STRONG)
        }
        override fun onResults(results: Bundle?) {
            val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
            if (!text.isNullOrBlank()) {
                transcript.text = text
                transcript.setTextColor(T.TEXT)
            } else {
                transcript.text = "no speech recognised"
            }
        }
        override fun onPartialResults(partialResults: Bundle?) {
            val text = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
            if (!text.isNullOrBlank()) transcript.text = text
        }
        override fun onEvent(eventType: Int, params: Bundle?) {}
    })

    fun startRecognition() {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            transcript.text = "Speech recognition is not available on this device."
            transcript.setTextColor(T.DANGER_STRONG)
            return
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "bn-IN")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        runCatching { speech.startListening(intent) }
            .onFailure { transcript.text = "could not start recognition: ${it.message}" }
    }

    // ---- text to speech -------------------------------------------------
    var tts: TextToSpeech? = null
    var ttsReady = false
    tts = TextToSpeech(context) { status ->
        ttsReady = status == TextToSpeech.SUCCESS
    }
    val bengaliAvailable = tts?.let { engine ->
        engine.isLanguageAvailable(Locale("bn", "IN"))
    } ?: TextToSpeech.LANG_NOT_SUPPORTED

    fun speakText(text: String) {
        if (text.isBlank() || !ttsReady) {
            transcript.text = "TTS is not ready on this device."
            return
        }
        tts?.language = Locale("bn", "IN")
        val code = tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "titan-${System.currentTimeMillis()}")
        transcript.text = if (code == TextToSpeech.ERROR) {
            "TTS failed for the selected language."
        } else {
            "speaking ($code)"
        }
    }

    // ---- capability reporting ------------------------------------------
    capabilityText.text = buildString {
        append("platform ASR available: ")
        append(SpeechRecognizer.isRecognitionAvailable(context))
        append("\nplatform TTS initialised: ")
        append(ttsReady)
        append("\nBengali TTS status: ")
        append(
            when (bengaliAvailable) {
                TextToSpeech.LANG_AVAILABLE -> "LANG_AVAILABLE"
                TextToSpeech.LANG_MISSING_DATA -> "LANG_MISSING_DATA (install the language pack)"
                TextToSpeech.LANG_NOT_SUPPORTED -> "LANG_NOT_SUPPORTED"
                else -> "unknown($bengaliAvailable)"
            })
        append("\nBengali is reported only from a live platform probe.")
    }

    Api.run(onSuccess = { json ->
        val server = JSONObject(json).optJSONObject("server")
        val detail = "server ASR engine installed: ${server?.optBoolean("whisper_cpp_binary") ?: false} · " +
            "server TTS engine installed: ${server?.optBoolean("piper_binary") ?: false}"
        capabilityText.append("\n" + detail)
    }, onError = { error ->
        capabilityText.append("\nserver capability probe failed: ${error.message}")
    }) { Api.get("/api/v1/voice/capabilities") }

    // Bind the controls once every handler is defined.
    talkButton.setOnClickListener {
        startCapture()
        startRecognition()
    }
    stopButton.setOnClickListener { stopCapture() }
    speakButton.setOnClickListener { speakText(transcript.text.toString()) }

    return scrollView(context, column)
}

/** Waveform rendered from real captured amplitudes. */
class WaveformView(context: android.content.Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = T.CYAN
        strokeWidth = 3f
        style = Paint.Style.STROKE
    }
    private val samples = ArrayList<Float>()
    private var active = false

    fun push(amplitude: Float) {
        synchronized(samples) {
            samples.add(amplitude.coerceIn(0f, 1f))
            if (samples.size > 600) samples.removeAt(0)
        }
        postInvalidate()
    }

    fun setActive(value: Boolean) {
        active = value
        postInvalidate()
    }

    val sampleCount: Int get() = synchronized(samples) { samples.size }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val centerY = height / 2f
        canvas.drawLine(0f, centerY, width.toFloat(), centerY, paint.apply { color = T.BORDER })
        val snapshot = synchronized(samples) { samples.toList() }
        if (snapshot.isEmpty()) {
            paint.color = T.TEXT_DISABLED
            canvas.drawCircle(width / 2f, centerY, 4f, paint.apply { style = Paint.Style.FILL })
            paint.style = Paint.Style.STROKE
            return
        }
        paint.color = if (active) T.CYAN else T.TEXT_SECONDARY
        val step = width.toFloat() / 600f
        var x = 0f
        for (sample in snapshot) {
            val amplitude = sample * (height / 2f - 8f)
            canvas.drawLine(x, centerY - amplitude, x, centerY + amplitude, paint)
            x += step
        }
    }
}

private fun space(context: android.content.Context, dp: Int): View =
    View(context).apply { layoutParams = lp(ViewGroup.LayoutParams.MATCH_PARENT, dp) }
