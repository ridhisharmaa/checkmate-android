package com.checkmate.app.ui

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.checkmate.app.network.ApiClient
import com.checkmate.app.network.QuestionOverridePatchRequest
import com.checkmate.app.network.SubmissionResult
import com.checkmate.app.network.uriToMultipart
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class GradingUiState(
    val teacherUris: List<Uri> = emptyList(),
    val studentUris: List<Uri> = emptyList(),
    val status: String = "idle",
    val currentStage: String? = null,
    val errorMessage: String? = null,
    val submissionId: String? = null,
    val result: SubmissionResult? = null,
    val isBusy: Boolean = false,
)

class GradingViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(GradingUiState())
    val uiState: StateFlow<GradingUiState> = _uiState

    fun setTeacherUris(uris: List<Uri>) = _uiState.update { it.copy(teacherUris = uris) }
    fun setStudentUris(uris: List<Uri>) = _uiState.update { it.copy(studentUris = uris) }

    /** Returns false (and sets an error) without starting anything if files aren't selected yet —
     * lets the caller (UploadScreen) decide whether to navigate based on a synchronous result. */
    fun startGrading(context: Context): Boolean {
        val current = _uiState.value
        if (current.teacherUris.isEmpty() || current.studentUris.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "Select at least one teacher file and one student file.") }
            return false
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isBusy = true, errorMessage = null, status = "uploading", result = null) }
            try {
                val teacherParts = current.teacherUris.map { uriToMultipart(context, it, "teacher_files") }
                val studentParts = current.studentUris.map { uriToMultipart(context, it, "student_files") }
                val response = ApiClient.service.createSubmission(teacherParts, studentParts)
                _uiState.update { it.copy(submissionId = response.submissionId, status = "queued") }
                pollJob(response.jobId, response.submissionId)
            } catch (e: Exception) {
                _uiState.update { it.copy(isBusy = false, status = "failed", errorMessage = describeError(e)) }
            }
        }
        return true
    }

    fun reset() {
        _uiState.value = GradingUiState()
    }

    private suspend fun pollJob(jobId: String, submissionId: String) {
        while (true) {
            val job = try {
                ApiClient.service.getJob(jobId)
            } catch (e: Exception) {
                _uiState.update { it.copy(isBusy = false, status = "failed", errorMessage = describeError(e)) }
                return
            }
            _uiState.update { it.copy(status = job.status, currentStage = job.currentStage) }

            when (job.status) {
                "failed" -> {
                    _uiState.update { it.copy(isBusy = false, errorMessage = job.errorMessage ?: "Grading failed") }
                    return
                }
                "done" -> {
                    loadResult(submissionId)
                    return
                }
                else -> delay(1500)
            }
        }
    }

    private suspend fun loadResult(submissionId: String) {
        try {
            val detail = ApiClient.service.getSubmission(submissionId)
            _uiState.update { it.copy(isBusy = false, result = detail.result) }
        } catch (e: Exception) {
            _uiState.update { it.copy(isBusy = false, errorMessage = describeError(e)) }
        }
    }

    fun overrideQuestion(questionResultId: String, choice: String) {
        val submissionId = _uiState.value.submissionId ?: return
        viewModelScope.launch {
            try {
                val detail = ApiClient.service.overrideQuestion(
                    submissionId, questionResultId, QuestionOverridePatchRequest(choice)
                )
                _uiState.update { it.copy(result = detail.result) }
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = describeError(e)) }
            }
        }
    }

    private fun describeError(e: Exception): String =
        e.message ?: e.javaClass.simpleName
}
