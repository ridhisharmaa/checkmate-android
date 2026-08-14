package com.checkmate.app.ui

import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController

private object Routes {
    const val Upload = "upload"
    const val Progress = "progress"
    const val Results = "results"
}

// One GradingViewModel shared across all three screens (created here, passed down) so
// upload/job/result state survives navigation without re-fetching or duplicating it per screen.
@Composable
fun CheckMateApp() {
    val viewModel: GradingViewModel = viewModel()
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = Routes.Upload) {
        composable(Routes.Upload) {
            UploadScreen(viewModel, onStarted = { navController.navigate(Routes.Progress) })
        }
        composable(Routes.Progress) {
            ProgressScreen(
                viewModel,
                onDone = { navController.navigate(Routes.Results) { popUpTo(Routes.Upload) } },
                onBack = { navController.popBackStack(Routes.Upload, inclusive = false) },
            )
        }
        composable(Routes.Results) {
            ResultsScreen(
                viewModel,
                onGradeAnother = {
                    viewModel.reset()
                    navController.popBackStack(Routes.Upload, inclusive = false)
                },
            )
        }
    }
}
