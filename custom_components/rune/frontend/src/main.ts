import "@shoelace-style/shoelace/dist/themes/light.css";

import { bootstrapI18n, installBridgeLocaleSync } from "./i18n.js";
import { initLocalePref } from "./state/locale-pref.js";
import { initTheme } from "./state/theme.js";
import { injectRootTokens } from "./styles/root-tokens.js";

import "./styles/shoelace-theme.js";
import "./components/ui/index.js";
import "./components/app-shell.js";

injectRootTokens();
initLocalePref();
initTheme();
void bootstrapI18n();
installBridgeLocaleSync();
