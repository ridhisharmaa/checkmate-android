package com.checkmate.app.ui.exam

import com.checkmate.app.ui.marks
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.RadioButtonUnchecked
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.checkmate.app.network.StudentSummary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExamDetailScreen(
    viewModel: ExamDetailViewModel,
    examId: String,
    onBack: () -> Unit,
    onUploadForStudent: (studentId: String, rollNumber: String) -> Unit,
    onViewSubmission: (submissionId: String) -> Unit,
) {
    val state by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(examId) { viewModel.load(examId) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(state.exam?.title ?: "Exam") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    if (state.exam != null) {
                        IconButton(onClick = { shareMarksCsv(context, state.exam!!.title, state.exam!!.students) }) {
                            Icon(Icons.Filled.FileDownload, contentDescription = "Export marks")
                        }
                    }
                },
            )
        },
    ) { padding ->
        when {
            state.isLoading && state.exam == null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            state.exam == null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Text(state.errorMessage ?: "Could not load this exam.")
            }
            else -> {
                val exam = state.exam!!
                Column(Modifier.fillMaxSize().padding(padding)) {
                    RosterHeader(
                        maxMarks = exam.maxMarks,
                        gradedCount = exam.students.count { it.status == "done" },
                        totalCount = exam.students.size,
                        onAddRange = viewModel::addRollRange,
                        onAddSingle = viewModel::addRollNumber,
                    )
                    HorizontalDivider()

                    if (exam.students.isEmpty()) {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text(
                                "No roll numbers yet — add a range above to build the roster.",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(24.dp),
                            )
                        }
                    } else {
                        LazyColumn(contentPadding = PaddingValues(vertical = 8.dp)) {
                            items(exam.students, key = { it.id }) { student ->
                                RosterRow(
                                    student = student,
                                    onClick = {
                                        if (student.status == "done" && student.submissionId != null) {
                                            onViewSubmission(student.submissionId)
                                        } else if (student.status == "not_uploaded") {
                                            onUploadForStudent(student.id, student.rollNumber)
                                        }
                                    },
                                    onRemove = if (student.status == "not_uploaded") {
                                        { viewModel.removeRollNumber(student.id) }
                                    } else null,
                                )
                            }
                        }
                    }

                    state.errorMessage?.let {
                        Text(
                            it,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(16.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun RosterHeader(
    maxMarks: Double?,
    gradedCount: Int,
    totalCount: Int,
    onAddRange: (Int, Int) -> Unit,
    onAddSingle: (String) -> Unit,
) {
    var start by remember { mutableStateOf("") }
    var end by remember { mutableStateOf("") }
    var single by remember { mutableStateOf("") }

    Column(Modifier.fillMaxWidth().padding(16.dp)) {
        Text(
            "$gradedCount / $totalCount graded" + if (maxMarks != null) " · out of ${maxMarks.marks()}" else "",
            style = MaterialTheme.typography.titleSmall,
        )
        Spacer(Modifier.height(12.dp))

        Text("Add roll numbers", style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(6.dp))
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = start,
                onValueChange = { start = it.filter(Char::isDigit) },
                label = { Text("Start") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.weight(1f),
            )
            OutlinedTextField(
                value = end,
                onValueChange = { end = it.filter(Char::isDigit) },
                label = { Text("End") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.weight(1f),
            )
            OutlinedButton(
                onClick = {
                    val s = start.toIntOrNull()
                    val e = end.toIntOrNull()
                    if (s != null && e != null) {
                        onAddRange(s, e)
                        start = ""
                        end = ""
                    }
                },
            ) { Text("Generate") }
        }

        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = single,
                onValueChange = { single = it },
                label = { Text("Add one roll number") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            OutlinedButton(
                onClick = {
                    if (single.isNotBlank()) {
                        onAddSingle(single.trim())
                        single = ""
                    }
                },
            ) { Text("Add") }
        }
    }
}

@Composable
private fun RosterRow(student: StudentSummary, onClick: () -> Unit, onRemove: (() -> Unit)?) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Roll ${student.rollNumber}", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            StatusChip(student)
            if (onRemove != null) {
                IconButton(onClick = onRemove) {
                    Icon(Icons.Filled.Close, contentDescription = "Remove", tint = MaterialTheme.colorScheme.outline)
                }
            }
        }
    }
}

@Composable
private fun StatusChip(student: StudentSummary) {
    when (student.status) {
        "done" -> Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(6.dp))
            Text(
                "${(student.totalScore ?: 0.0).marks()}/${(student.maxScore ?: 0.0).marks()} (${student.gradeLetter ?: ""})",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        "queued", "running" -> Row(verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
            Spacer(Modifier.width(6.dp))
            Text("Grading…", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        "failed" -> Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.Error, contentDescription = null, tint = MaterialTheme.colorScheme.error)
            Spacer(Modifier.width(6.dp))
            Text("Failed", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
        }
        else -> Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Filled.RadioButtonUnchecked,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.outline,
                modifier = Modifier.size(20.dp),
            )
            Spacer(Modifier.width(6.dp))
            Text("Not uploaded", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
