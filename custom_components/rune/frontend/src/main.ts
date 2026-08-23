import "@shoelace-style/shoelace/dist/themes/light.css";

import { bootstrapI18n, installBridgeLocaleSync } from "./i18n.js";
import { initTheme } from "./state/theme.js";

import "./styles/shoelace-theme.js";
import "./components/ui/index.js";
import "./components/app-shell.js";

void bootstrapI18n();
installBridgeLocaleSync();
initTheme();
