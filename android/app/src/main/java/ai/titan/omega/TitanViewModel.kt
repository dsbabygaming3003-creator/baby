package ai.titan.omega

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import ai.titan.core.network.AgentDto
import ai.titan.core.network.ResearchTaskDto
import ai.titan.core.network.SystemStatus
import ai.titan.core.network.TitanRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class TitanUiState(
    val loading: Boolean = true,
    val system: SystemStatus? = null,
    val agents: List<AgentDto> = emptyList(),
    val research: ResearchTaskDto? = null,
    val chat: String = "",
    val error: String? = null,
    val working: Boolean = false,
)

class TitanViewModel(private val repository: TitanRepository) : ViewModel() {
    private val mutableState = MutableStateFlow(TitanUiState())
    val state: StateFlow<TitanUiState> = mutableState.asStateFlow()

    init { refresh() }

    fun refresh() = viewModelScope.launch {
        mutableState.value = mutableState.value.copy(loading = true, error = null)
        runCatching {
            val system = repository.system()
            val agents = repository.agents()
            system to agents
        }.onSuccess { (system, agents) ->
            mutableState.value = mutableState.value.copy(system = system, agents = agents, loading = false)
        }.onFailure {
            mutableState.value = mutableState.value.copy(loading = false, error = it.message ?: "Backend unavailable")
        }
    }

    fun research(query: String) = viewModelScope.launch {
        if (query.isBlank()) return@launch
        mutableState.value = mutableState.value.copy(working = true, error = null)
        runCatching { repository.research(query) }
            .onSuccess { mutableState.value = mutableState.value.copy(research = it, working = false) }
            .onFailure { mutableState.value = mutableState.value.copy(working = false, error = it.message) }
    }

    fun chat(message: String) = viewModelScope.launch {
        if (message.isBlank()) return@launch
        mutableState.value = mutableState.value.copy(working = true, error = null)
        runCatching { repository.chat(message) }
            .onSuccess {
                val prefix = if (it.is_mock) "[EXPLICIT MOCK]\n" else "[${it.provider}]\n"
                mutableState.value = mutableState.value.copy(chat = prefix + it.content, working = false)
            }
            .onFailure { mutableState.value = mutableState.value.copy(working = false, error = it.message) }
    }

    class Factory(private val repository: TitanRepository) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = TitanViewModel(repository) as T
    }
}
