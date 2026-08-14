package com.checkmate.app.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

@Composable
fun UploadScreen(viewModel: GradingViewModel, onStarted: () -> Unit) {
    val state by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    val teacherPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        viewModel.setTeacherUris(uris)
    }
    val studentPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        viewModel.setStudentUris(uris)
    }

    Column(modifier = Modifier.fillMaxSize().padding(20.dp)) {
        Text("Upload sheets", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(4.dp))
        Text(
            "Camera capture and batch upload aren't wired up yet — choose files from storage for now.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
        )
        Spacer(Modifier.height(28.dp))

        Text("Answer key (question paper + marking scheme)", style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = { teacherPicker.launch("*/*") }, modifier = Modifier.fillMaxWidth()) {
            Text(if (state.teacherUris.isEmpty()) "Choose files" else "${state.teacherUris.size} file(s) selected")
        }

        Spacer(Modifier.height(24.dp))
        Text("Student answer sheet", style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = { studentPicker.launch("*/*") }, modifier = Modifier.fillMaxWidth()) {
            Text(if (state.studentUris.isEmpty()) "Choose files" else "${state.studentUris.size} file(s) selected")
        }

        state.errorMessage?.let {
            Spacer(Modifier.height(16.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }

        Spacer(Modifier.weight(1f))
        Button(
            onClick = { if (viewModel.startGrading(context)) onStarted() },
            enabled = !state.isBusy,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Start grading")
        }
    }
}
