package com.checkmate.app.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.checkmate.app.network.QuestionGradeResult

@Composable
fun QuestionCard(q: QuestionGradeResult, onOverride: (String) -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(q.path.joinToString(" / "), style = MaterialTheme.typography.titleSmall)
            Text(q.questionText, style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(4.dp))
            Text("Reference: ${q.modelAnswer}", style = MaterialTheme.typography.bodySmall)
            Text(
                "Student: ${if (q.attempted) q.studentAnswer ?: "" else "Not attempted"}",
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "Score: ${q.finalScore} / ${q.maxMarks}" + if (!q.countedTowardTotal) " (not counted)" else "",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text("Feedback: ${q.feedback}", style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(6.dp))
            Row {
                TextButton(onClick = { onOverride("full") }) { Text("Full") }
                TextButton(onClick = { onOverride("half") }) { Text("Half") }
                TextButton(onClick = { onOverride("no_credit") }) { Text("None") }
            }
        }
    }
}
