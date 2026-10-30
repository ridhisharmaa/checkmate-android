package com.checkmate.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.checkmate.app.network.ApiClient
import com.checkmate.app.network.LoginRequest
import com.checkmate.app.network.SignupRequest
import com.checkmate.app.network.TokenStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class AuthUiState(
    val email: String = "",
    val password: String = "",
    val isBusy: Boolean = false,
    val errorMessage: String? = null,
    val loggedIn: Boolean = false,
)

class AuthViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState

    fun setEmail(value: String) = _uiState.update { it.copy(email = value, errorMessage = null) }
    fun setPassword(value: String) = _uiState.update { it.copy(password = value, errorMessage = null) }

    fun login() = runAuthCall { ApiClient.service.login(LoginRequest(_uiState.value.email.trim(), _uiState.value.password)) }

    fun signup() = runAuthCall { ApiClient.service.signup(SignupRequest(_uiState.value.email.trim(), _uiState.value.password)) }

    private fun runAuthCall(call: suspend () -> com.checkmate.app.network.TokenResponse) {
        val current = _uiState.value
        if (current.email.isBlank() || current.password.isBlank()) {
            _uiState.update { it.copy(errorMessage = "Enter an email and password.") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isBusy = true, errorMessage = null) }
            try {
                val token = call()
                TokenStore.saveToken(token.accessToken)
                _uiState.update { it.copy(isBusy = false, loggedIn = true) }
            } catch (e: Exception) {
                _uiState.update { it.copy(isBusy = false, errorMessage = describeError(e)) }
            }
        }
    }

    private fun describeError(e: Exception): String = when {
        e is HttpException && e.code() == 401 -> "Incorrect email or password."
        e is HttpException && e.code() == 409 -> "An account with this email already exists."
        else -> e.message ?: e.javaClass.simpleName
    }
}
