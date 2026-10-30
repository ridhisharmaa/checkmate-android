package com.checkmate.app.ui.exam

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.checkmate.app.network.ApiClient
import com.checkmate.app.network.AddRollNumberRequest
import com.checkmate.app.network.ExamDetailResponse
import com.checkmate.app.network.RollRangeRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class ExamDetailUiState(
    val exam: ExamDetailResponse? = null,
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
)

class ExamDetailViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(ExamDetailUiState())
    val uiState: StateFlow<ExamDetailUiState> = _uiState

    private lateinit var examId: String

    fun load(examId: String) {
        this.examId = examId
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            try {
                val exam = ApiClient.service.getExam(examId)
                _uiState.update { it.copy(isLoading = false, exam = exam) }
            } catch (e: Exception) {
                _uiState.update { it.copy(isLoading = false, errorMessage = e.message ?: e.javaClass.simpleName) }
            }
        }
    }

    /** Silent refresh (no loading spinner) — used after grading a submission or
     * mutating the roster, where the screen is already showing data. */
    private fun refresh() {
        viewModelScope.launch {
            try {
                val exam = ApiClient.service.getExam(examId)
                _uiState.update { it.copy(exam = exam) }
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = e.message ?: e.javaClass.simpleName) }
            }
        }
    }

    fun addRollRange(start: Int, end: Int) {
        viewModelScope.launch {
            try {
                ApiClient.service.addRollRange(examId, RollRangeRequest(start, end))
                refresh()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = describeError(e)) }
            }
        }
    }

    fun addRollNumber(rollNumber: String) {
        viewModelScope.launch {
            try {
                ApiClient.service.addRollNumber(examId, AddRollNumberRequest(rollNumber))
                refresh()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = describeError(e)) }
            }
        }
    }

    fun removeRollNumber(studentId: String) {
        viewModelScope.launch {
            try {
                ApiClient.service.removeRollNumber(examId, studentId)
                refresh()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = describeError(e)) }
            }
        }
    }

    /** Called after returning from a capture/upload or results screen, so the roster's
     * status chips reflect whatever just happened without a full reload flash. */
    fun onReturnedToScreen() = refresh()

    private fun describeError(e: Exception): String = when {
        e is HttpException && e.code() == 409 -> "That roll number already has a submission and can't be removed."
        else -> e.message ?: e.javaClass.simpleName
    }
}
