package titan.omega.infinity.net

import android.os.Handler
import android.os.Looper
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/**
 * Minimal HTTP client for the TITAN backend.
 *
 * The app is a first-class API client: every screen renders data that the
 * server actually returned. There is no bundled mock content.
 */
object Api {

    @Volatile var baseUrl: String = "http://10.0.2.2:8000"
    @Volatile var token: String? = null

    private val executor = Executors.newFixedThreadPool(4)
    private val main = Handler(Looper.getMainLooper())

    class HttpException(val code: Int, val body: String) : Exception("HTTP $code: ${body.take(300)}")

    /** Runs [block] on a background thread and delivers the result on the UI thread. */
    fun <T> async(onError: (Throwable) -> Unit = {}, block: () -> T): Unit {
        executor.execute {
            try {
                val result = block()
                main.post { @Suppress("UNCHECKED_CAST") (result as? Any)?.let { } }
            } catch (t: Throwable) {
                main.post { onError(t) }
            }
        }
    }

    /**
     * Runs [block] on a background thread; [onSuccess] and [onError] are always
     * delivered on the UI thread.
     */
    fun <T> run(onSuccess: (T) -> Unit, onError: (Throwable) -> Unit = {}, block: () -> T) {
        executor.execute {
            try {
                val value = block()
                main.post { onSuccess(value) }
            } catch (t: Throwable) {
                main.post { onError(t) }
            }
        }
    }

    fun connect(path: String, method: String = "GET", body: String? = null): HttpURLConnection {
        val url = URL(baseUrl + path)
        val connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 15000
        connection.readTimeout = 120000
        connection.setRequestProperty("Accept", "application/json")
        token?.let { connection.setRequestProperty("Authorization", "Bearer $it") }
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
        }
        return connection
    }

    fun get(path: String): String {
        val connection = connect(path)
        return try {
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) throw HttpException(code, text)
            text
        } finally {
            connection.disconnect()
        }
    }

    fun post(path: String, body: String): String {
        val connection = connect(path, "POST", body)
        return try {
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) throw HttpException(code, text)
            text
        } finally {
            connection.disconnect()
        }
    }

    /**
     * Server-sent-events stream. [onDelta] receives text fragments as they
     * arrive, [onDone] receives the terminal metadata and [onError] the failure.
     */
    fun streamSse(
        path: String,
        onDelta: (String) -> Unit,
        onDone: (String) -> Unit,
        onError: (Throwable) -> Unit
    ) {
        executor.execute {
            try {
                val connection = connect(path)
                connection.setRequestProperty("Accept", "text/event-stream")
                val code = connection.responseCode
                if (code !in 200..299) {
                    val text = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                    throw HttpException(code, text)
                }
                BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { reader ->
                    var event = ""
                    while (true) {
                        val line = reader.readLine() ?: break
                        when {
                            line.startsWith("event:") -> event = line.removePrefix("event:").trim()
                            line.startsWith("data:") -> {
                                val data = line.removePrefix("data:").trim()
                                main.post {
                                    when (event) {
                                        "delta" -> onDelta(data)
                                        "done" -> onDone(data)
                                        "error" -> onError(HttpException(500, data))
                                    }
                                }
                            }
                        }
                    }
                }
                connection.disconnect()
            } catch (t: Throwable) {
                main.post { onError(t) }
            }
        }
    }

    fun quote(value: String): String {
        val escaped = value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
        return "\"$escaped\""
    }
}
