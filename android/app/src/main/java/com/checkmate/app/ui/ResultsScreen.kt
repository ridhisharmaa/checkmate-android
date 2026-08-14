package com.checkmate.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.checkmate.app.network.SubmissionResult
import com.checkmate.app.ui.components.QuestionCard

private val TAB_TITLES = listOf("Overview", "Questions", "Notes")

@Composable
fun ResultsScreen(viewModel: GradingViewModel, onGradeAnother: () -> Unit) {
    val state by viewModel.uiState.collectAsState()
    val result = state.result

    if (result == null) {
        // Shouldn't normally happen (navigation only fires once state.result is set), but
        // avoids a crash if the screen is somehow reached before the result loads.
        Column(Modifier.fillMaxSize().padding(24.dp)) {
            Text("No result yet.", style = MaterialTheme.typography.bodyLarge)
        }
        return
    }

    var selectedTab by remember { mutableStateOf(0) }

    Column(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxWidth().padding(20.dp)) {
            Text("Results", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(4.dp))
            Text("${result.totalScore} / ${result.maxScore}", style = MaterialTheme.typography.displaySmall)
            Text("Grade: ${result.gradeLetter}", style = MaterialTheme.typography.titleMedium)
        }

        TabRow(selectedTabIndex = selectedTab) {
            TAB_TITLES.forEachIndexed { index, title ->
                Tab(selected = selectedTab == index, onClick = { selectedTab = index }, text = { Text(title) })
            }
        }

        Column(Modifier.weight(1f)) {
            when (selectedTab) {
                0 -> OverviewTab(result)
                1 -> QuestionsTab(result, onOverride = { id, choice -> viewModel.overrideQuestion(id, choice) })
                else -> NotesTab()
            }
        }

        Button(onClick = onGradeAnother, modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text("Grade another sheet")
        }
    }
}

@Composable
private fun OverviewTab(result: SubmissionResult) {
    Column(
        modifier = Modifier.fillMaxSize().padding(20.dp).verticalScroll(rememberScrollState()),
    ) {
        Text(
            "Handwriting confidence: ${(result.handwritingConfidence * 100).toInt()}%",
            style = MaterialTheme.typography.titleMedium,
        )
        Spacer(Modifier.height(20.dp))

        Text("Strengths", style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(4.dp))
        if (result.overview.strengths.isEmpty()) {
            Text("None noted.", style = MaterialTheme.typography.bodyMedium)
        } else {
            result.overview.strengths.forEach { Text("• $it") }
        }

        Spacer(Modifier.height(20.dp))
        Text("Watch for", style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(4.dp))
        if (result.overview.watchFor.isEmpty()) {
            Text("None noted.", style = MaterialTheme.typography.bodyMedium)
        } else {
            result.overview.watchFor.forEach { Text("• $it") }
        }
    }
}

@Composable
private fun QuestionsTab(result: SubmissionResult, onOverride: (String, String) -> Unit) {
    LazyColumn(modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        items(result.results) { q ->
            QuestionCard(q, onOverride = { choice -> q.id?.let { onOverride(it, choice) } })
        }
    }
}

@Composable
private fun NotesTab() {
    // Local-only for now — there's no backend field/endpoint for submission notes yet,
    // so nothing typed here survives navigating away. Wire up a real endpoint before
    // relying on this for anything that needs to persist.
    var notes by remember { mutableStateOf("") }
    Column(modifier = Modifier.fillMaxSize().padding(20.dp)) {
        Text(
            "Local notes only for now — not saved to the backend yet.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = notes,
            onValueChange = { notes = it },
            modifier = Modifier.fillMaxSize(),
            placeholder = { Text("Write notes about this submission...") },
        )
    }
}
