package com.checkmate.app.ui.exam

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.checkmate.app.network.ApiClient
import com.checkmate.app.network.toPlainRequestBody
import com.checkmate.app.network.uriToMultipart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class CreateExamUiState(
    val title: String = "",
    val subject: String = "",
    val answerKeyUris: List<Uri> = emptyList(),
    val isBusy: Boolean = false,
    val errorMessage: String? = null,
    val createdExamId: String? = null,
)

class CreateExamViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(CreateExamUiState())
    val uiState: StateFlow<CreateExamUiState> = _uiState

    fun setTitle(value: String) = _uiState.update { it.copy(title = value, errorMessage = null) }
    fun setSubject(value: String) = _uiState.update { it.copy(subject = value) }
    fun setAnswerKeyUris(uris: List<Uri>) = _uiState.update { it.copy(answerKeyUris = uris, errorMessage = null) }

    fun createExam(context: Context) {
        val current = _uiState.value
        if (current.title.isBlank()) {
            _uiState.update { it.copy(errorMessage = "Give this exam a title.") }
            return
        }
        if (current.answerKeyUris.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "Upload the answer key (question paper + marking scheme).") }
            return
        }

        val appContext = context.applicationContext
        viewModelScope.launch {
            // Parsing the answer key is a real OCR call — this can take a while.
            _uiState.update { it.copy(isBusy = true, errorMessage = null) }
            try {
                val parts = withContext(Dispatchers.IO) {
                    current.answerKeyUris.map { uriToMultipart(appContext, it, "answer_key_files") }
                }
                val exam = ApiClient.service.createExam(
                    current.title.toPlainRequestBody(),
                    current.subject.toPlainRequestBody(),
                    parts,
                )
                _uiState.update { it.copy(isBusy = false, createdExamId = exam.id) }
            } catch (e: Exception) {
                _uiState.update { it.copy(isBusy = false, errorMessage = e.message ?: e.javaClass.simpleName) }
            }
        }
    }
}
