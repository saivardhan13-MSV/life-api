package com.saivardhan.lifeapi.screentime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SessionsTest {
    private val min = 60_000L
    private val start = 1_000 * min
    private val end = start + 1440 * min
    private fun on(pkg: String, t: Long) = FgEvent(pkg, Sessions.RESUMED, t)
    private fun off(pkg: String, t: Long) = FgEvent(pkg, Sessions.PAUSED, t)

    @Test
    fun sumsSessionsPerApp() {
        val ev = listOf(
            on("ig", start + 10 * min), off("ig", start + 40 * min),
            on("yt", start + 50 * min), off("yt", start + 60 * min),
            on("ig", start + 100 * min), off("ig", start + 115 * min),
        )
        val r = Sessions.foregroundMillis(ev, start, end, now = end + min)
        assertEquals(45 * min, r["ig"])
        assertEquals(10 * min, r["yt"])
    }

    @Test
    fun clipsSessionThatStartedBeforeMidnight() {
        val ev = listOf(on("ig", start - 20 * min), off("ig", start + 5 * min))
        assertEquals(5 * min, Sessions.foregroundMillis(ev, start, end, now = end)["ig"])
    }

    @Test
    fun openSessionCountsUntilNow() {
        val ev = listOf(on("ig", start + 10 * min))
        val r = Sessions.foregroundMillis(ev, start, end, now = start + 25 * min)
        assertEquals(15 * min, r["ig"])
    }

    @Test
    fun ignoresPauseWithoutResumeAndOutOfOrderEvents() {
        val ev = listOf(
            off("ig", start + 5 * min),
            off("yt", start + 30 * min), on("yt", start + 20 * min), // unsorted input
        )
        val r = Sessions.foregroundMillis(ev, start, end, now = end)
        assertTrue("ig" !in r)
        assertEquals(10 * min, r["yt"])
    }

    @Test
    fun activitySwitchInsideSameAppDoesNotDoubleCount() {
        val ev = listOf(
            on("ig", start), on("ig", start + 5 * min), // second activity resumes before first pauses
            off("ig", start + 10 * min),
        )
        assertEquals(10 * min, Sessions.foregroundMillis(ev, start, end, now = end)["ig"])
    }
}
