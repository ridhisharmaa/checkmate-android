package com.checkmate.app.ui

import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.checkmate.app.network.TokenStore
import com.checkmate.app.ui.auth.AuthViewModel
import com.checkmate.app.ui.auth.LoginScreen
import com.checkmate.app.ui.auth.SignupScreen
import com.checkmate.app.ui.capture.CaptureScreen
import com.checkmate.app.ui.exam.CreateExamScreen
import com.checkmate.app.ui.exam.CreateExamViewModel
import com.checkmate.app.ui.exam.ExamDetailScreen
import com.checkmate.app.ui.exam.ExamDetailViewModel
import com.checkmate.app.ui.home.HomeScreen
import com.checkmate.app.ui.home.HomeViewModel

private object Routes {
    const val Login = "login"
    const val Signup = "signup"
    const val Home = "home"
    const val CreateExam = "createExam"
    const val ExamDetail = "examDetail/{examId}"
    const val Capture = "capture/{examId}/{studentId}/{rollNumber}"
    const val Progress = "progress"
    const val Results = "results"
    const val ExistingResults = "existingResults/{examId}/{submissionId}"

    fun examDetail(examId: String) = "examDetail/$examId"
    fun capture(examId: String, studentId: String, rollNumber: String) = "capture/$examId/$studentId/$rollNumber"
    fun existingResults(examId: String, submissionId: String) = "existingResults/$examId/$submissionId"
}

// GradingViewModel is shared across the capture -> progress -> results screens (and reused,
// via loadExisting, for viewing an already-graded submission) so its polling/result state
// survives navigation between them without re-fetching or duplicating it per screen.
@Composable
fun CheckMateApp() {
    val navController = rememberNavController()
    val gradingViewModel: GradingViewModel = viewModel()

    val startDestination = if (TokenStore.getToken() != null) Routes.Home else Routes.Login

    NavHost(navController = navController, startDestination = startDestination) {
        composable(Routes.Login) {
            LoginScreen(
                viewModel<AuthViewModel>(),
                onLoggedIn = {
                    navController.navigate(Routes.Home) { popUpTo(Routes.Login) { inclusive = true } }
                },
                onGoToSignup = { navController.navigate(Routes.Signup) },
            )
        }
        composable(Routes.Signup) {
            SignupScreen(
                viewModel<AuthViewModel>(),
                onSignedUp = {
                    navController.navigate(Routes.Home) { popUpTo(Routes.Login) { inclusive = true } }
                },
                onGoToLogin = { navController.popBackStack() },
            )
        }
        composable(Routes.Home) {
            HomeScreen(
                viewModel<HomeViewModel>(),
                onCreateExam = { navController.navigate(Routes.CreateExam) },
                onOpenExam = { examId -> navController.navigate(Routes.examDetail(examId)) },
                onLogout = {
                    TokenStore.clear()
                    navController.navigate(Routes.Login) { popUpTo(0) { inclusive = true } }
                },
            )
        }
        composable(Routes.CreateExam) {
            CreateExamScreen(
                viewModel<CreateExamViewModel>(),
                onCreated = { examId ->
                    navController.navigate(Routes.examDetail(examId)) { popUpTo(Routes.Home) { inclusive = false } }
                },
                onBack = { navController.popBackStack() },
            )
        }
        composable(
            Routes.ExamDetail,
            arguments = listOf(navArgument("examId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val examId = backStackEntry.arguments?.getString("examId").orEmpty()
            ExamDetailScreen(
                viewModel<ExamDetailViewModel>(),
                examId = examId,
                onBack = {
                    navController.navigate(Routes.Home) { popUpTo(Routes.Home) { inclusive = true } }
                },
                onUploadForStudent = { studentId, rollNumber ->
                    gradingViewModel.startForStudent(examId, studentId)
                    navController.navigate(Routes.capture(examId, studentId, rollNumber))
                },
                onViewSubmission = { submissionId ->
                    navController.navigate(Routes.existingResults(examId, submissionId))
                },
            )
        }
        composable(
            Routes.Capture,
            arguments = listOf(
                navArgument("examId") { type = NavType.StringType },
                navArgument("studentId") { type = NavType.StringType },
                navArgument("rollNumber") { type = NavType.StringType },
            ),
        ) { backStackEntry ->
            val rollNumber = backStackEntry.arguments?.getString("rollNumber").orEmpty()
            CaptureScreen(
                gradingViewModel,
                rollNumber = rollNumber,
                onSubmitted = { navController.navigate(Routes.Progress) },
                onBack = { navController.popBackStack() },
            )
        }
        composable(Routes.Progress) {
            ProgressScreen(
                gradingViewModel,
                onDone = { navController.navigate(Routes.Results) { popUpTo(Routes.Progress) { inclusive = true } } },
                onBack = {
                    val examId = gradingViewModel.uiState.value.examId
                    if (examId != null) {
                        navController.navigate(Routes.examDetail(examId)) { popUpTo(Routes.Home) { inclusive = false } }
                    } else {
                        navController.navigate(Routes.Home) { popUpTo(Routes.Home) { inclusive = true } }
                    }
                },
            )
        }
        composable(Routes.Results) {
            ResultsScreen(
                gradingViewModel,
                onGradeAnother = {
                    val examId = gradingViewModel.uiState.value.examId
                    gradingViewModel.reset()
                    if (examId != null) {
                        navController.navigate(Routes.examDetail(examId)) { popUpTo(Routes.Home) { inclusive = false } }
                    } else {
                        navController.navigate(Routes.Home) { popUpTo(Routes.Home) { inclusive = true } }
                    }
                },
            )
        }
        composable(
            Routes.ExistingResults,
            arguments = listOf(
                navArgument("examId") { type = NavType.StringType },
                navArgument("submissionId") { type = NavType.StringType },
            ),
        ) { backStackEntry ->
            val examId = backStackEntry.arguments?.getString("examId").orEmpty()
            val submissionId = backStackEntry.arguments?.getString("submissionId").orEmpty()
            ExistingResultsScreen(
                gradingViewModel,
                submissionId = submissionId,
                onBack = {
                    navController.navigate(Routes.examDetail(examId)) { popUpTo(Routes.Home) { inclusive = false } }
                },
            )
        }
    }
}
