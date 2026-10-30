package com.checkmate.app.ui.exam

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import com.checkmate.app.network.StudentSummary
import java.io.File

fun shareMarksCsv(context: Context, examTitle: String, students: List<StudentSummary>) {
    val csv = buildString {
        appendLine("roll_number,status,total_score,max_score,grade_letter")
        students
            .sortedBy { it.rollNumber.toIntOrNull() ?: Int.MAX_VALUE }
            .forEach { s ->
                appendLine(
                    listOf(
                        s.rollNumber, s.status, s.totalScore?.toString().orEmpty(),
                        s.maxScore?.toString().orEmpty(), s.gradeLetter.orEmpty(),
                    ).joinToString(","),
                )
            }
    }

    val dir = File(context.cacheDir, "exports").apply { mkdirs() }
    val safeTitle = examTitle.replace(Regex("[^A-Za-z0-9_-]+"), "_").take(40).ifBlank { "exam" }
    val file = File(dir, "marks_$safeTitle.csv")
    file.writeText(csv)

    val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/csv"
        putExtra(Intent.EXTRA_STREAM, uri)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(Intent.createChooser(intent, "Share marks"))
}
