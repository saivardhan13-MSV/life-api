package com.saivardhan.lifeapi.screentime

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.IOException
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit

/**
 * Uploads the last N days (default 2: yesterday's final numbers + today so far).
 * Today is re-sent on every run and simply replaces the earlier partial upload.
 */
class SyncWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val prefs = Prefs(applicationContext)
        val stamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("MMM d, HH:mm"))
        if (!prefs.isConfigured) {
            prefs.lastStatus = "$stamp: not set up (enter API URL and key)"
            return@withContext Result.failure()
        }
        if (!UsageCollector.hasPermission(applicationContext)) {
            prefs.lastStatus = "$stamp: usage access not granted"
            return@withContext Result.failure()
        }

        val days = inputData.getInt(KEY_DAYS, 2).coerceIn(1, 10)
        val today = LocalDate.now()
        val lines = mutableListOf<String>()
        try {
            for (i in days - 1 downTo 0) {
                val day = today.minusDays(i.toLong())
                val apps = UsageCollector.collect(applicationContext, day)
                if (apps.isEmpty()) continue
                Uploader.upload(prefs.apiUrl, prefs.apiKey, day, apps)
                val total = apps.sumOf { it.minutes }.toInt()
                lines += "$day: ${total / 60}h ${total % 60}m across ${apps.size} apps"
            }
            prefs.lastStatus = "Last sync $stamp ✓\n" + lines.joinToString("\n").ifEmpty { "No usage recorded yet" }
            Result.success()
        } catch (e: ApiException) {
            prefs.lastStatus = "$stamp: server said ${e.message}" + if (e.code == 401) " (check the API key)" else ""
            if (e.code in 500..599) Result.retry() else Result.failure()
        } catch (e: IOException) {
            prefs.lastStatus = "$stamp: network error, will retry (${e.message})"
            Result.retry()
        }
    }

    companion object {
        const val KEY_DAYS = "days"
        private const val PERIODIC = "screen-time-sync"
        private const val NOW = "screen-time-sync-now"
        private val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        fun schedule(context: Context) {
            val req = PeriodicWorkRequestBuilder<SyncWorker>(6, TimeUnit.HOURS)
                .setConstraints(network)
                .setInputData(workDataOf(KEY_DAYS to 2))
                .build()
            WorkManager.getInstance(context)
                .enqueueUniquePeriodicWork(PERIODIC, ExistingPeriodicWorkPolicy.UPDATE, req)
        }

        fun syncNow(context: Context, days: Int) {
            val req = OneTimeWorkRequestBuilder<SyncWorker>()
                .setConstraints(network)
                .setInputData(workDataOf(KEY_DAYS to days))
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(NOW, ExistingWorkPolicy.REPLACE, req)
        }
    }
}
