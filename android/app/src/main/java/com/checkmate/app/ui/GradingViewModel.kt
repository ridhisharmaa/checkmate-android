package com.checkmate.app.ui

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.checkmate.app.network.ApiClient
import com.checkmate.app.network.QuestionOverridePatchRequest
import com.checkmate.app.network.SubmissionResult
import com.checkmate.app.network.uriToMultipart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class GradingUiState(
    val examId: String? = null,
    val studentId: String? = null,
    val pageUris: List<Uri> = emptyList(),
    val status: String = "idle",
    val currentStage: String? = null,
    val errorMessage: String? = null,
    val submissionId: String? = null,
    val result: SubmissionResult? = null,
    val isBusy: Boolean = false,
)

/** Shared across the capture -> progress -> results screens for a single submission,
 * and also used (via [loadExisting]) to view an already-graded submission directly
 * from the exam roster, skipping the upload/poll steps entirely. */
class GradingViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(GradingUiState())
    val uiState: StateFlow<GradingUiState> = _uiState

    fun startForStudent(examId: String, studentId: String) {
        _uiState.value = GradingUiState(examId = examId, studentId = studentId)
    }

    fun setPageUris(uris: List<Uri>) = _uiState.update { it.copy(pageUris = uris, errorMessage = null) }

    fun addPageUri(uri: Uri) = _uiState.update { it.copy(pageUris = it.pageUris + uri, errorMessage = null) }

    fun addPageUris(uris: List<Uri>) = _uiState.update { it.copy(pageUris = it.pageUris + uris, errorMessage = null) }

    fun removeLastPage() = _uiState.update { it.copy(pageUris = it.pageUris.dropLast(1)) }

    /** Returns false (and sets an error) without starting anything if no pages are
     * captured/picked yet — lets the caller (CaptureScreen) decide whether to
     * navigate based on a synchronous result. */
    fun submit(context: Context): Boolean {
        val current = _uiState.value
        val examId = current.examId
        val studentId = current.studentId
        if (examId == null || studentId == null) {
            _uiState.update { it.copy(errorMessage = "Missing exam/roll number context.") }
            return false
        }
        if (current.pageUris.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "Capture or choose at least one page.") }
            return false
        }

        // Application context, not the Activity's: this outlives the coroutine's caller
        // and holding the Activity would leak it across a rotation.
        val appContext = context.applicationContext

        viewModelScope.launch {
            _uiState.update { it.copy(isBusy = true, errorMessage = null, status = "uploading", result = null) }
            try {
                // viewModelScope defaults to Dispatchers.Main, so reading the picked
                // files here would read whole multi-megabyte images on the UI thread.
                val parts = withContext(Dispatchers.IO) {
                    current.pageUris.map { uriToMultipart(appContext, it, "student_files") }
                }
                val response = ApiClient.service.createSubmission(examId, studentId, parts)
                _uiState.update { it.copy(submissionId = response.submissionId, status = "queued") }
                pollJob(response.jobId, response.submissionId)
            } catch (e: Exception) {
                _uiState.update { it.copy(isBusy = false, status = "failed", errorMessage = describeError(e)) }
            }
        }
        return true
    }

    /** Skips capture/upload/poll entirely — used when the teacher taps an already-graded
     * roll number in the exam roster and just wants to view/override its result. */
    fun loadExisting(submissionId: String) {
        _uiState.value = GradingUiState(submissionId = submissionId, isBusy = true)
        viewModelScope.launch { loadResult(submissionId) }
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
            if (detail.result == null) {
                // Job says done but the payload has no result — treat as a failure
                // rather than sitting on the progress screen forever.
                _uiState.update {
                    it.copy(isBusy = false, status = "failed", errorMessage = "Grading finished but returned no result.")
                }
                return
            }
            _uiState.update { it.copy(isBusy = false, status = "done", result = detail.result) }
        } catch (e: Exception) {
            // Must mark the status failed, not just set a message: the progress screen
            // now waits for a result before navigating, and only renders an error in
            // the "failed" state — otherwise a fetch error would hang on that screen.
            _uiState.update { it.copy(isBusy = false, status = "failed", errorMessage = describeError(e)) }
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
