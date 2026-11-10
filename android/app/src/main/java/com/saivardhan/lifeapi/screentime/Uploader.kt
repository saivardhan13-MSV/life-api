package com.saivardhan.lifeapi.screentime

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate

class ApiException(val code: Int, message: String) : IOException(message)

object Uploader {
    /** POST /v1/screen-time. Re-sending a day replaces it on the server, so retries are safe. */
    fun upload(apiUrl: String, apiKey: String, day: LocalDate, apps: List<AppUsage>) {
        val body = JSONObject()
            .put("day", day.toString())
            .put(
                "apps",
                JSONArray().apply {
                    apps.take(500).forEach { a ->
                        put(
                            JSONObject()
                                .put("package", a.pkg)
                                .put("app_name", a.name ?: JSONObject.NULL)
                                .put("minutes", Math.round(a.minutes * 100) / 100.0),
                        )
                    }
                },
            )

        val conn = URL(apiUrl.trimEnd('/') + "/v1/screen-time").openConnection() as HttpURLConnection
        try {
            conn.requestMethod = "POST"
            conn.connectTimeout = 15_000
            conn.readTimeout = 30_000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("X-API-Key", apiKey)
            conn.outputStream.use { it.write(body.toString().toByteArray()) }
            val code = conn.responseCode
            if (code !in 200..299) {
                val err = conn.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
                throw ApiException(code, "HTTP $code ${err.take(200)}")
            }
        } finally {
            conn.disconnect()
        }
    }
}
