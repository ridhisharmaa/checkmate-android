package com.checkmate.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.RadioButtonUnchecked
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

// Matches the approved grading-progress mockup's 5-step checklist exactly. Driven by real
// GradingJob.current_stage values polled from the backend — no client-side fake timer.
private val STEPS = listOf(
    "uploading" to "Uploading images",
    "detecting_handwriting" to "Detecting handwriting",
    "matching_to_answer_key" to "Matching to answer key",
    "grading_responses" to "Grading responses",
    "generating_summary" to "Generating summary",
)

private fun currentStepIndex(status: String, stage: String?): Int = when {
    status == "uploading" || status == "queued" -> 0
    stage == "detecting_handwriting" -> 1
    stage == "matching_to_answer_key" -> 2
    stage == "grading_responses" -> 3
    stage == "generating_summary" -> 4
    status == "done" -> 5
    else -> 0
}

private enum class StepState { Done, Active, Pending }

@Composable
fun ProgressScreen(viewModel: GradingViewModel, onDone: () -> Unit, onBack: () -> Unit) {
    val state by viewModel.uiState.collectAsState()

    LaunchedEffect(state.status) {
        if (state.status == "done") onDone()
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Grading in progress", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(32.dp))

        val stepIndex = currentStepIndex(state.status, state.currentStage)
        Column(modifier = Modifier.fillMaxWidth()) {
            STEPS.forEachIndexed { index, (_, label) ->
                val stepState = when {
                    state.status == "failed" && index == stepIndex -> StepState.Pending
                    index < stepIndex -> StepState.Done
                    index == stepIndex -> StepState.Active
                    else -> StepState.Pending
                }
                StepRow(label, stepState)
            }
        }

        if (state.status == "failed") {
            Spacer(Modifier.height(24.dp))
            Text(
                "Grading failed: ${state.errorMessage ?: "unknown error"}",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium,
            )
            Spacer(Modifier.height(16.dp))
            Button(onClick = onBack) { Text("Back to upload") }
        }
    }
}

@Composable
private fun StepRow(label: String, state: StepState) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
    ) {
        when (state) {
            StepState.Done -> Icon(
                Icons.Filled.CheckCircle,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
            )
            StepState.Active -> CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
            StepState.Pending -> Icon(
                Icons.Filled.RadioButtonUnchecked,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.outline,
            )
        }
        Spacer(Modifier.width(12.dp))
        Text(
            label,
            style = if (state == StepState.Active) MaterialTheme.typography.bodyLarge else MaterialTheme.typography.bodyMedium,
        )
    }
}
