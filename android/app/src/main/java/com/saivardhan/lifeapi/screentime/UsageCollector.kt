package com.saivardhan.lifeapi.screentime

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Process
import java.time.LocalDate
import java.time.ZoneId

data class AppUsage(val pkg: String, val name: String?, val minutes: Double)

object UsageCollector {
    private const val LOOKBACK_MS = 3 * 60 * 60 * 1000L // catch sessions that started before midnight
    private const val MIN_MINUTES = 0.5

    fun hasPermission(context: Context): Boolean {
        val ops = context.getSystemService(AppOpsManager::class.java)
        val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ops.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName)
        } else {
            @Suppress("DEPRECATION")
            ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName)
        }
        return mode == AppOpsManager.MODE_ALLOWED
    }

    /** Per-app foreground minutes for one local calendar day, biggest first. */
    fun collect(context: Context, day: LocalDate): List<AppUsage> {
        val zone = ZoneId.systemDefault()
        val start = day.atStartOfDay(zone).toInstant().toEpochMilli()
        val end = day.plusDays(1).atStartOfDay(zone).toInstant().toEpochMilli()
        val now = System.currentTimeMillis()

        val usm = context.getSystemService(UsageStatsManager::class.java)
        val iter = usm.queryEvents(start - LOOKBACK_MS, minOf(end, now))
        val events = ArrayList<FgEvent>()
        val e = UsageEvents.Event()
        while (iter.hasNextEvent()) {
            iter.getNextEvent(e)
            if (e.eventType == Sessions.RESUMED || e.eventType == Sessions.PAUSED) {
                events += FgEvent(e.packageName, e.eventType, e.timeStamp)
            }
        }

        val excluded = excludedPackages(context)
        val pm = context.packageManager
        return Sessions.foregroundMillis(events, start, end, now)
            .filterKeys { it !in excluded }
            .map { (pkg, ms) -> AppUsage(pkg, label(pm, pkg), minOf(ms / 60000.0, 1440.0)) }
            .filter { it.minutes >= MIN_MINUTES }
            .sortedByDescending { it.minutes }
    }

    /** The home screen, the system UI and this app itself are not "screen time". */
    private fun excludedPackages(context: Context): Set<String> {
        val home = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
        val launchers = context.packageManager
            .queryIntentActivities(home, PackageManager.MATCH_DEFAULT_ONLY)
            .map { it.activityInfo.packageName }
        return launchers.toSet() + setOf(context.packageName, "com.android.systemui")
    }

    private fun label(pm: PackageManager, pkg: String): String? = try {
        pm.getApplicationLabel(pm.getApplicationInfo(pkg, 0)).toString()
    } catch (_: PackageManager.NameNotFoundException) {
        null
    }
}
