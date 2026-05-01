"""
Chart Loader Fix — Session 12 (01-May-26)
==========================================

Bug: charts work on file:// but not on GitHub Pages.

Root cause: loadChartData uses XHR + eval(xhr.responseText) which executes inside
the IIFE's local scope. The chart file's `var CHART_REGISTRY=CHART_REGISTRY||{}`
creates an IIFE-local variable that shadows the global window.CHART_REGISTRY.
Within the IIFE the local registry IS populated, but the eval scoping is fragile —
especially in strict-mode IIFEs ("use strict") where var-hoisting through eval
behaves differently.

On file://, Chrome happens to make this work. On GitHub Pages over HTTPS the same
path fails: registry stays empty, drawChart gets null data, panel shows "No chart
data for X".

Fix: replace XHR+eval with pure script-tag injection. <script src> always executes
at GLOBAL scope, populating window.CHART_REGISTRY directly — which is what the
chart files were designed for (`var CHART_REGISTRY=CHART_REGISTRY||{}` at top of
each file is a no-op assign of the global to itself, then the assignment lands on
the global). Manual script injection has been verified to work on GitHub Pages.

Also: tighten chart panel right padding so the price-axis labels don't sit flush
against the panel edge.
"""
import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "build_dashboard.py"


def backup():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = SCRIPT_DIR / f"build_dashboard.py.bak-pre-chartfix-{ts}"
    shutil.copy2(TARGET, bak)
    print(f"  Backup: {bak.name}")


def apply(src, anchor, new_text, label):
    n = src.count(anchor)
    if n != 1:
        print(f"  FAIL [{label}]: anchor count = {n} (expected 1)")
        sys.exit(1)
    print(f"  OK [{label}]")
    return src.replace(anchor, new_text)


def main():
    print(f"Reading {TARGET}...")
    src = TARGET.read_text(encoding="utf-8")
    print(f"  Original: {len(src):,} bytes")
    backup()

    # ─────────────────────────────────────────────────────────────
    # Edit 1: Replace loadChartData body with pure script-tag injection.
    # The current implementation uses XHR + eval which fails silently on GitHub Pages
    # due to IIFE-local scope. Pure script injection executes at global scope and works.
    # ─────────────────────────────────────────────────────────────
    old_load = '''function loadChartData(ticker, callback){
  // Already loaded?
  if(CHART_REGISTRY[ticker]){
    callback(_expandChartRows(CHART_REGISTRY[ticker]));
    return;
  }
  // Already loading?
  if(_chartLoading[ticker]){
    _chartLoading[ticker].push(callback);
    return;
  }
  _chartLoading[ticker]=[callback];
  var url="charts/"+_safeTickerFile(ticker)+".js";
  // Try XHR first (works from file:// and http://), fall back to script injection
  var xhr=new XMLHttpRequest();
  xhr.open("GET",url,true);
  xhr.onreadystatechange=function(){
    if(xhr.readyState!==4)return;
    if(xhr.status===200||(xhr.status===0&&xhr.responseText)){
      try{eval(xhr.responseText)}catch(e){}
      var cbs=_chartLoading[ticker]||[];
      delete _chartLoading[ticker];
      var data=CHART_REGISTRY[ticker]?_expandChartRows(CHART_REGISTRY[ticker]):null;
      for(var i=0;i<cbs.length;i++)cbs[i](data);
    }else{
      // XHR returned non-200 (e.g. 404) — fall back to script injection
      var s2=document.createElement("script");
      s2.src=url;
      s2.onload=function(){
        var cbs3=_chartLoading[ticker]||[];
        delete _chartLoading[ticker];
        var data3=CHART_REGISTRY[ticker]?_expandChartRows(CHART_REGISTRY[ticker]):null;
        for(var i=0;i<cbs3.length;i++)cbs3[i](data3);
      };
      s2.onerror=function(){
        var cbs3=_chartLoading[ticker]||[];
        delete _chartLoading[ticker];
        for(var i=0;i<cbs3.length;i++)cbs3[i](null);
      };
      document.head.appendChild(s2);
    }
  };
  try{xhr.send()}catch(e){
    // XHR blocked entirely (file:// on some browsers) — fall back to script injection
    var s=document.createElement("script");
    s.src=url;
    s.onload=function(){
      var cbs2=_chartLoading[ticker]||[];'''

    # Find the close of the function. The structure continues. Let me match more conservatively
    # by anchoring on a unique signature near the start of loadChartData.
    # The anchor above ends mid-stream; let me grab the full function via different anchor.

    # Simpler approach: find from "function loadChartData" to its closing brace.
    func_start_marker = "function loadChartData(ticker, callback){"
    if src.count(func_start_marker) != 1:
        print("  FAIL [1]: loadChartData declaration not found uniquely")
        sys.exit(1)
    start_idx = src.index(func_start_marker)
    # Walk forward to find balanced closing brace
    depth = 0
    end_idx = -1
    in_str = None
    i = start_idx
    n = len(src)
    while i < n:
        c = src[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
        else:
            if c == '"' or c == "'":
                in_str = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        i += 1
    if end_idx < 0:
        print("  FAIL [1]: could not find balanced close of loadChartData")
        sys.exit(1)

    new_load = '''function loadChartData(ticker, callback){
  // SESSION 12 D-MD-CHART-1: pure script-tag injection. XHR+eval path failed silently
  // on GitHub Pages because eval(xhr.responseText) runs in IIFE-local scope, and the
  // chart file's `var CHART_REGISTRY=CHART_REGISTRY||{}` shadows the global registry.
  // Script-tag injection executes at GLOBAL scope and writes to window.CHART_REGISTRY directly.
  // Already loaded?
  if(CHART_REGISTRY[ticker]){
    callback(_expandChartRows(CHART_REGISTRY[ticker]));
    return;
  }
  // Already loading?
  if(_chartLoading[ticker]){
    _chartLoading[ticker].push(callback);
    return;
  }
  _chartLoading[ticker]=[callback];
  var url="charts/"+_safeTickerFile(ticker)+".js";
  var s=document.createElement("script");
  s.src=url;
  s.onload=function(){
    var cbs=_chartLoading[ticker]||[];
    delete _chartLoading[ticker];
    var data=CHART_REGISTRY[ticker]?_expandChartRows(CHART_REGISTRY[ticker]):null;
    for(var i=0;i<cbs.length;i++)cbs[i](data);
  };
  s.onerror=function(){
    var cbs=_chartLoading[ticker]||[];
    delete _chartLoading[ticker];
    for(var i=0;i<cbs.length;i++)cbs[i](null);
  };
  document.head.appendChild(s);
}'''

    old_full = src[start_idx:end_idx]
    src = src[:start_idx] + new_load + src[end_idx:]
    print(f"  OK [1: replace loadChartData ({len(old_full)} -> {len(new_load)} chars)]")

    # ─────────────────────────────────────────────────────────────
    # Edit 2: Adjust chart-panel padding so price-axis labels don't sit flush
    # against the right edge. Current padding:16px; bump right padding to 24px.
    # ─────────────────────────────────────────────────────────────
    src = apply(
        src,
        ".chart-panel{position:fixed;top:var(--header-height);right:0;bottom:0;width:25%;background:var(--card);border-left:1px solid var(--border);z-index:90;transform:translateX(100%);transition:transform .3s ease,width .3s ease;overflow-y:auto;padding:16px}",
        ".chart-panel{position:fixed;top:var(--header-height);right:0;bottom:0;width:25%;background:var(--card);border-left:1px solid var(--border);z-index:90;transform:translateX(100%);transition:transform .3s ease,width .3s ease;overflow-y:auto;padding:16px 24px 16px 16px}",
        "2: chart panel right padding",
    )

    new_size = len(src)
    print(f"  New: {new_size:,} bytes")
    TARGET.write_text(src, encoding="utf-8")

    print("Verifying py_compile...")
    import py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("  OK")
    except py_compile.PyCompileError as e:
        print(f"  FAIL: {e}")
        sys.exit(1)
    print("\nDONE. Run: python build_dashboard.py")


if __name__ == "__main__":
    main()
