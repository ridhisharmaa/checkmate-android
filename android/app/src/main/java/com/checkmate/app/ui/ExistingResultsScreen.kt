package com.checkmate.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

/** Thin wrapper around [ResultsScreen] for viewing a submission that was already graded
 * earlier (tapped from the exam roster) — loads it directly via [GradingViewModel.loadExisting]
 * instead of going through the capture -> upload -> poll flow. */
@Composable
fun ExistingResultsScreen(viewModel: GradingViewModel, submissionId: String, onBack: () -> Unit) {
    val state by viewModel.uiState.collectAsState()

    LaunchedEffect(submissionId) { viewModel.loadExisting(submissionId) }

    when {
        state.result != null -> ResultsScreen(viewModel, onGradeAnother = onBack)
        state.errorMessage != null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text(state.errorMessage ?: "", color = MaterialTheme.colorScheme.error)
        }
        else -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
    }
}
