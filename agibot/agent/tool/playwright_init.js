(function patchDetection() {
    // Patch navigator properties
    Object.defineProperty(navigator, 'webdriver', { get: () => false });

    delete navigator.seleniumWebdriver;
    delete navigator.driver;
    delete navigator.selenium;

    // Patch global window leaks
    delete window.domAutomation;
    delete window.domAutomationController;
    delete window._WEBDRIVER_ELEM_CACHE;
    delete window.callPhantom;
    delete window._phantom;
    delete window.__nightmare;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

    // Override Function.prototype.toString to hide Puppeteer/Playwright markers
    const originalToString = Function.prototype.toString;
    Function.prototype.toString = function () {
        const result = originalToString.call(this);
        return result
            .replace(/__puppeteer_evaluation_script__/g, '')
            .replace(/__playwright_evaluation_script__/g, '');
    };

    // Patch navigator.userAgent to hide "Headless"
    const originalUserAgent = navigator.userAgent;
    Object.defineProperty(navigator, 'userAgent', {
        get: () => originalUserAgent.replace(/HeadlessChrome|headless/gi, 'Chrome')
    });

    // Patch WebGLRenderingContext.getParameter to spoof renderer & vendor
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function (param) {
        const ext = this.getExtension('WEBGL_debug_renderer_info');
        if (param === ext.UNMASKED_VENDOR_WEBGL) {
            return "Google Inc. (NVIDIA)";
        }
        if (param === ext.UNMASKED_RENDERER_WEBGL) {
            return "ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 (0x00002704) Direct3D11 vs_5_0 ps_5_0, D3D11)";
        }
        return getParameter.call(this, param);
    };
})();