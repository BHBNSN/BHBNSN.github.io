# 应用启动流程
## 1. 为什么你能点开一个 App？
我们每天看到的桌面实际上也是一个 App，叫做 Launcher（启动器），位于 `/packages/apps/Launcher3/`。
图标点击事件由 BubbleTextView 或 ShortcutAndWidgetContainer 传递到 Launcher，再走 startActivitySafely() → AMS。
```java title="Launcher3 启动 App 代码"
@Override
public RunnableList startActivitySafely(View v, Intent intent, ItemInfo item) {
    if (!hasBeenResumed()) {
        RunnableList result = new RunnableList();
        // Workaround an issue where the WM launch animation is clobbered when finishing the
        // recents animation into launcher. Defer launching the activity until Launcher is
        // next resumed.
        addEventCallback(EVENT_RESUMED, () -> {
            RunnableList actualResult = startActivitySafely(v, intent, item);
            if (actualResult != null) {
                actualResult.add(result::executeAllAndDestroy);
            } else {
                result.executeAllAndDestroy();
            }
        });
        if (mOnDeferredActivityLaunchCallback != null) {
            mOnDeferredActivityLaunchCallback.run();
            mOnDeferredActivityLaunchCallback = null;
        }
        return result;
    }
    
    RunnableList result = super.startActivitySafely(v, intent, item);
    if (result != null && v instanceof BubbleTextView) {
        // This is set to the view that launched the activity that navigated the user away
        // from launcher. Since there is no callback for when the activity has finished
        // launching, enable the press state and keep this reference to reset the press
        // state when we return to launcher.
        BubbleTextView btv = (BubbleTextView) v;
        btv.setStayPressed(true);
        result.add(() -> btv.setStayPressed(false));
    }
    return result;
}
```
