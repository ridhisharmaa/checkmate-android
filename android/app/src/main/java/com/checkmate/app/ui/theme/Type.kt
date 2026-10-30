package com.checkmate.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.font.FontWeight

// Default system font, just weighted a bit heavier for headlines than Material3's
// stock type scale — this app is read on a phone at arm's length in a staff room,
// titles need to be gettable at a glance.
val CheckMateTypography = Typography().let { base ->
    base.copy(
        headlineSmall = base.headlineSmall.copy(fontWeight = FontWeight.SemiBold),
        titleLarge = base.titleLarge.copy(fontWeight = FontWeight.SemiBold),
        titleMedium = base.titleMedium.copy(fontWeight = FontWeight.Medium),
    )
}
