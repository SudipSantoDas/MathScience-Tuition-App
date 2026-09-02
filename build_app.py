import webview

# We configure the app window with private storage settings to bypass the locked folder bug
window = webview.create_window(
    'MathScience Academy', 
    'https://mathscience-tuition-app-79wufkk3dwwumx2xgicyed.streamlit.app/'
)

# The 'private_mode=False' parameter prevents pywebview from trying to force-delete locked system folders on boot
webview.start(private_mode=False)