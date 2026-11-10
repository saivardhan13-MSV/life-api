package com.saivardhan.lifeapi.screentime

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    private lateinit var prefs: Prefs
    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        prefs = Prefs(this)

        val url = findViewById<EditText>(R.id.apiUrl)
        val key = findViewById<EditText>(R.id.apiKey)
        url.setText(prefs.apiUrl)
        key.setText(prefs.apiKey)

        fun save(): Boolean {
            prefs.apiUrl = url.text.toString().trim()
            prefs.apiKey = key.text.toString().trim()
            if (!prefs.isConfigured) {
                Toast.makeText(this, "Enter an https:// API URL and your API key", Toast.LENGTH_LONG).show()
                return false
            }
            SyncWorker.schedule(this)
            return true
        }

        findViewById<Button>(R.id.grantButton).setOnClickListener {
            startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
        }
        findViewById<Button>(R.id.saveButton).setOnClickListener {
            if (save()) Toast.makeText(this, "Saved. Syncing every 6 hours.", Toast.LENGTH_SHORT).show()
        }
        findViewById<Button>(R.id.syncButton).setOnClickListener {
            if (!save()) return@setOnClickListener
            SyncWorker.syncNow(this, days = 7)
            findViewById<TextView>(R.id.lastStatus).text = "Syncing…"
            pollStatus(remaining = 15)
        }
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun refresh() {
        val ok = UsageCollector.hasPermission(this)
        findViewById<TextView>(R.id.permissionStatus).text =
            if (ok) "✓ Usage access granted" else "✗ Usage access needed: tap below, find \"Life API Screen Time\", turn it on"
        findViewById<Button>(R.id.grantButton).text = if (ok) "Usage access settings" else "Grant usage access"
        findViewById<TextView>(R.id.lastStatus).text = prefs.lastStatus
    }

    private fun pollStatus(remaining: Int) {
        if (remaining <= 0) return
        handler.postDelayed({
            refresh()
            if (findViewById<TextView>(R.id.lastStatus).text.toString() == "Syncing…") pollStatus(remaining - 1)
        }, 2000)
    }
}
