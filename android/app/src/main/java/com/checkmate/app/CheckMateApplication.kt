package com.checkmate.app

import android.app.Application
import com.checkmate.app.network.TokenStore

class CheckMateApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        TokenStore.init(this)
    }
}
