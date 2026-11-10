package com.saivardhan.lifeapi.screentime

import android.content.Context

/** App-private settings. The API key never leaves this app except in the X-API-Key header. */
class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("life_api", Context.MODE_PRIVATE)
    private val defaultUrl = context.getString(R.string.default_api_url)

    var apiUrl: String
        get() = sp.getString("api_url", null) ?: defaultUrl
        set(v) = sp.edit().putString("api_url", v).apply()

    var apiKey: String
        get() = sp.getString("api_key", "") ?: ""
        set(v) = sp.edit().putString("api_key", v).apply()

    var lastStatus: String
        get() = sp.getString("last_status", "Not synced yet") ?: ""
        set(v) = sp.edit().putString("last_status", v).apply()

    val isConfigured: Boolean get() = apiUrl.startsWith("https://") && apiKey.isNotBlank()
}
