package com.capzo.ia

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private val siteUrl = "https://capzo-ia.onrender.com"

    // Connexions OAuth : ouvertes dans le navigateur système, jamais dans la WebView.
    private val navigateurExterne = listOf(
        "accounts.google.com", "oauth2.googleapis.com", "github.com",
        "www.github.com", "facebook.com", "www.facebook.com",
        "tiktok.com", "www.tiktok.com"
    )

    private var selectionFichier: ValueCallback<Array<Uri>>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        webView = WebView(this)
        setContentView(webView)

        val ws: WebSettings = webView.settings
        ws.javaScriptEnabled = true
        ws.domStorageEnabled = true
        ws.mediaPlaybackRequiresUserGesture = false
        ws.allowFileAccess = false
        ws.useWideViewPort = true
        ws.loadWithOverviewMode = true
        ws.setSupportZoom(false)
        WebView.setWebContentsDebuggingEnabled(false)

        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView?,
                callback: ValueCallback<Array<Uri>>?,
                params: FileChooserParams?
            ): Boolean {
                selectionFichier?.onReceiveValue(null)
                selectionFichier = callback
                val intent = Intent(Intent.ACTION_GET_CONTENT)
                intent.addCategory(Intent.CATEGORY_OPENABLE)
                intent.type = params?.acceptTypes?.firstOrNull()?.takeIf { it.isNotBlank() } ?: "*/*"
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                startActivityForResult(Intent.createChooser(intent, "Choisir un fichier"), 1001)
                return true
            }
        }

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url.toString()
                val hote = request.url.host ?: ""
                when {
                    navigateurExterne.any { hote == it || hote.endsWith(".$it") } -> {
                        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                        return true
                    }
                    url.startsWith("tel:") || url.startsWith("sms:") ||
                    url.startsWith("mailto:") || url.startsWith("whatsapp:") ||
                    url.startsWith("intent:") -> {
                        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                        return true
                    }
                }
                return false
            }
        }

        handleIntent(intent)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != 1001) return
        val callback = selectionFichier ?: return
        selectionFichier = null
        val resultats = mutableListOf<Uri>()
        data?.clipData?.let { clip ->
            for (i in 0 until clip.itemCount) resultats.add(clip.getItemAt(i).uri)
        } ?: data?.data?.let { resultats.add(it) }
        callback.onReceiveValue(
            if (resultCode == Activity.RESULT_OK && resultats.isNotEmpty())
                resultats.toTypedArray() else emptyArray()
        )
    }

    private fun handleIntent(intent: Intent?) {
        val data = intent?.data
        when {
            data != null && data.toString().startsWith(siteUrl) -> webView.loadUrl(data.toString())
            intent?.action == Intent.ACTION_SEND -> {
                val texte = intent.getStringExtra(Intent.EXTRA_TEXT)
                val uri = intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
                if (uri != null) {
                    webView.loadUrl("$siteUrl/?partage_media=${Uri.encode(uri.toString())}")
                } else if (texte != null) {
                    webView.loadUrl("$siteUrl/?partage_texte=${Uri.encode(texte)}")
                } else {
                    webView.loadUrl(siteUrl)
                }
            }
            else -> webView.loadUrl(siteUrl)
        }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }
}
