package com.saivardhan.lifeapi.screentime

/** A foreground/background transition for one app. Pure data so it can be unit tested. */
data class FgEvent(val pkg: String, val type: Int, val time: Long)

object Sessions {
    // Same values as UsageEvents.Event.ACTIVITY_RESUMED / ACTIVITY_PAUSED.
    const val RESUMED = 1
    const val PAUSED = 2

    /**
     * Foreground milliseconds per package inside [start, end).
     *
     * Sessions that began before the window are clipped to it; a session still
     * open at the end is counted up to min(end, now). A pause with no matching
     * resume (the app was opened before the events we queried) is ignored.
     */
    fun foregroundMillis(events: List<FgEvent>, start: Long, end: Long, now: Long): Map<String, Long> {
        val open = HashMap<String, Long>()
        val total = HashMap<String, Long>()

        fun add(pkg: String, from: Long, to: Long) {
            val s = maxOf(from, start)
            val e = minOf(to, end)
            if (e > s) total[pkg] = (total[pkg] ?: 0L) + (e - s)
        }

        for (ev in events.sortedBy { it.time }) {
            when (ev.type) {
                RESUMED -> if (!open.containsKey(ev.pkg)) open[ev.pkg] = ev.time
                PAUSED -> open.remove(ev.pkg)?.let { add(ev.pkg, it, ev.time) }
            }
        }
        val cutoff = minOf(end, now)
        open.forEach { (pkg, from) -> add(pkg, from, cutoff) }
        return total
    }
}
