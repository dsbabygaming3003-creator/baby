package ai.titan.core.network

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType

@Serializable
data class SystemCounts(
    val agents: Int = 0,
    val research_tasks: Int = 0,
    val projects: Int = 0,
    val workflows: Int = 0,
)

@Serializable
data class SystemStatus(
    val name: String,
    val version: String,
    val status: String,
    val environment: String,
    val authentication: String,
    val database: String,
    val counts: SystemCounts,
)

@Serializable
data class AgentDto(
    val id: String,
    val name: String,
    val description: String,
    val role: String,
    val version: String,
    val status: String,
    val timeout_seconds: Int,
)

@Serializable
data class ResearchRequestDto(
    val query: String,
    val connectors: List<String> = listOf("github"),
    val max_results: Int = 5,
    val wait: Boolean = true,
)

@Serializable
data class ResearchTaskDto(
    val id: String,
    val query: String,
    val status: String,
    val error: String? = null,
    val report_path: String? = null,
)

@Serializable
data class ConversationDto(val id: String, val title: String)

@Serializable
data class ConversationCreateDto(val title: String = "New chat")

@Serializable
data class MessageCreateDto(
    val content: String,
    val route: String = "chat",
)

@Serializable
data class MessageDto(
    val id: String,
    val role: String,
    val content: String,
    val provider: String? = null,
    val model: String? = null,
    val is_mock: Boolean = false,
    val status: String,
)

interface TitanApi {
    @GET("api/v1/system")
    suspend fun system(): SystemStatus

    @GET("api/v1/agents")
    suspend fun agents(): List<AgentDto>

    @POST("api/v1/research/tasks")
    suspend fun research(@Body request: ResearchRequestDto): ResearchTaskDto

    @POST("api/v1/conversations")
    suspend fun createConversation(@Body request: ConversationCreateDto): ConversationDto

    @POST("api/v1/conversations/{id}/messages")
    suspend fun sendMessage(@Path("id") id: String, @Body request: MessageCreateDto): MessageDto
}

object TitanApiFactory {
    fun create(baseUrl: String): TitanApi {
        require(baseUrl.startsWith("https://") || baseUrl.startsWith("http://10.0.2.2")) {
            "Only HTTPS endpoints (or the Android emulator debug host) are permitted"
        }
        val contentType = "application/json".toMediaType()
        val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
        val client = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .build()
        return Retrofit.Builder()
            .baseUrl(if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/")
            .client(client)
            .addConverterFactory(json.asConverterFactory(contentType))
            .build()
            .create(TitanApi::class.java)
    }
}

class TitanRepository(private val api: TitanApi) {
    suspend fun system() = api.system()
    suspend fun agents() = api.agents()
    suspend fun research(query: String) = api.research(ResearchRequestDto(query))
    suspend fun chat(message: String): MessageDto {
        val conversation = api.createConversation(ConversationCreateDto())
        return api.sendMessage(conversation.id, MessageCreateDto(message))
    }
}
