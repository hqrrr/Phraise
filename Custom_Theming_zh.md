# 自定义主题

PhrAIse 内置了九种配色主题，从 Catppuccin Mocha、Nord Dark 等深色主题，到 GitHub Light、Catppuccin Latte 等浅色主题。你可以在设置面板中切换主题，也可以叠加自定义 CSS 实现更精细的控制。下文会介绍这两种方式，以及如何在源码中添加全新的主题色板。

## 概览

主题系统位于 [`phraise/theme.py`](phraise/theme.py)。它将两部分内容分离：

- **配色色板**：由 18 个命名颜色键组成的字典，用于生成应用程序样式表。
- **自定义 CSS**：一段自由格式的 CSS 代码，保存在设置中，并追加在生成好的样式表之后，因此始终具有最高优先级。

这意味着你可以选择内置主题、编写一段 CSS 覆盖，或者通过修改几个 Python 文件定义一整套新色板。

## 选择主题

1. 右键点击悬浮球或托盘图标，选择 **设置**。
2. 切换到 **外观** 标签页。
3. 在 **主题** 下拉菜单中选择一个主题。
4. 点击 **保存**。
5. 重启 PhrAIse。新主题会在下次启动时生效。

所选主题保存在 `%APPDATA%/PhrAIse/settings.json` 中的 `appearance.theme` 字段下。

## 内置主题

PhrAIse 包含五种深色主题和四种浅色主题。

### 深色主题

| 名称 | 预览 |
|------|------|
| Catppuccin Mocha | <img src="docs/theme/catppuccin-mocha.png" alt="theme-catppuccin-mocha" width="150"/> |
| One Dark Pro | <img src="docs/theme/one-dark-pro.png" alt="theme-one-dark-pro" width="150"/> |
| Solarized Dark | <img src="docs/theme/solarized-dark.png" alt="theme-solarized-dark" width="150"/> |
| Nord Dark | <img src="docs/theme/nord-dark.png" alt="theme-nord-dark" width="150"/> |
| Monokai | <img src="docs/theme/monokai.png" alt="theme-monokai" width="150"/> |

### 浅色主题

| 名称 | 预览 |
|------|------|
| Catppuccin Latte | <img src="docs/theme/catppuccin-latte.png" alt="theme-catppuccin-latte" width="150"/> |
| Solarized Light | <img src="docs/theme/solarized-light.png" alt="theme-solarized-light" width="150"/> |
| GitHub Light | <img src="docs/theme/github-light.png" alt="theme-github-light" width="150"/> |
| One Light | <img src="docs/theme/one-light.png" alt="theme-one-light" width="150"/> |

## 自定义 CSS 覆盖

外观标签页中有一个 **自定义 CSS** 编辑器。你在其中输入的任何内容都会保存到 `settings.json` 的 `appearance.custom_css` 字段下，并在 [`phraise/theme.py`](phraise/theme.py) 的 `apply_theme()` 中被追加到生成好的样式表之后。由于它是最后追加的，因此你的规则会覆盖默认样式。

### 编辑与预览

- 在编辑器中输入 CSS。
- 点击 **验证** 检查括号是否配对。状态标签会显示大括号是否平衡。
- 点击 **预览** 在一个小示例窗口中渲染应用了你的 CSS 的效果。
- 保存并重启 PhrAIse，即可在整个应用中看到完整效果。

### 示例

下面这段代码让所有按钮变圆、改变强调色的边框颜色，并将文本编辑区的背景变暗：

```css
QPushButton {
    border-radius: 8px;
}

QComboBox {
    border: 2px solid rgb(108, 92, 231);
}

QTextEdit {
    background: rgb(17, 17, 27);
}
```

你可以使用十六进制颜色、`rgb()`，或者直接复用当前主题中的颜色值。自定义 CSS 块使用标准 Qt 样式表语法，因此任何有效的 Qt 选择器都可以使用。

## 创建新主题色板

如果你想在源码中添加新主题，而不是在界面里用 CSS 补丁，可以新建一个色板文件并注册它。

### 1. 添加色板文件

从 [`phraise/theme_palettes/`](phraise/theme_palettes/) 复制一个现有的色板文件，例如 [`phraise/theme_palettes/catppuccin_mocha.py`](phraise/theme_palettes/catppuccin_mocha.py)，然后重命名：

```text
phraise/theme_palettes/my_theme.py
```

### 2. 填写 18 个必需的颜色

将颜色值替换为你自己的。每个主题都必须定义以下键，完整列表见 [`phraise/theme.py`](phraise/theme.py) 中的 `MANDATORY_COLOR_KEYS`：

```python
colors = {
    "bg": "#1e1e2e",
    "bg_darker": "#181825",
    "surface": "#313244",
    "surface_hover": "#45475a",
    "border": "#45475a",
    "ball_border": "#11111b",
    "text": "#cdd6f4",
    "text_muted": "#a6adc8",
    "text_dim": "#6c7086",
    "accent": "#6c5ce7",
    "accent_hover": "#9b8fff",
    "red": "#f38ba8",
    "red_hover": "#f06292",
    "orange": "#fab387",
    "green": "#a6e3a1",
    "yellow": "#f9e2af",
    "white": "#ffffff",
    "grip": "#585b70",
}

theme = {"colors": colors, "sizing": DEFAULT_SIZING}
```

### 3. 注册主题

打开 [`phraise/theme.py`](phraise/theme.py)，在文件顶部附近添加对新色板的导入，然后把它加入 `THEMES` 注册表：

```python
THEMES: dict[str, FullTheme] = {
    "Catppuccin Mocha": catppuccin_mocha.theme,
    ...
    "My Theme": my_theme.theme,
}
```

### 4. 标记为深色或浅色主题

如果你的主题是深色的，还需要把显示名称加入 [`phraise/theme.py`](phraise/theme.py) 中的 `_DARK_THEMES` frozenset：

```python
_DARK_THEMES: frozenset[str] = frozenset({
    "Catppuccin Mocha",
    ...
    "My Theme",
})
```

浅色主题只需要加入 `THEMES` 即可，无需额外配置。

### 5. 重启 PhrAIse

重启后，新主题就会出现在 **主题** 下拉菜单中。

## 主题颜色参考

18 个 `MANDATORY_COLOR_KEYS` 及其作用：

| 键 | 作用 |
|----|------|
| `bg` | 主应用背景色 |
| `bg_darker` | 输入框和标题栏等较深背景色 |
| `surface` | 卡片和控件的凸起表面背景色 |
| `surface_hover` | 可交互表面的悬停状态背景色 |
| `border` | 框架和输入框的默认边框颜色 |
| `ball_border` | 悬浮球的边框颜色 |
| `text` | 主要文本颜色 |
| `text_muted` | 次要/弱化文本颜色 |
| `text_dim` | 第三级/禁用状态文本颜色 |
| `accent` | 主要强调色，用于激活/选中项 |
| `accent_hover` | 强调色元素的悬停状态 |
| `red` | 错误/危险指示色 |
| `red_hover` | 红色/危险元素的悬停状态 |
| `orange` | 警告/高亮指示色 |
| `green` | 成功/正面指示色 |
| `yellow` | 注意/中性高亮色 |
| `white` | 纯白色，用于强调色背景上的高对比文本 |
| `grip` | 拖拽手柄/调整大小抓手颜色 |

## CSS 选择器提示

PhrAIse 使用标准 Qt 样式表。以下选择器覆盖了最常用的控件：

| 选择器 | 目标 |
|--------|------|
| `QWidget` | 通用背景或字体默认值 |
| `QPushButton` | 按钮，包括主按钮和示例按钮 |
| `QLineEdit` | 单行文本输入框 |
| `QTextEdit` | 多行文本编辑器，包括自定义 CSS 编辑器 |
| `QComboBox` | 下拉选择器，例如主题选择器 |
| `QComboBox::drop-down` | 下拉箭头区域 |
| `QComboBox QAbstractItemView` | 下拉弹出列表 |
| `QScrollBar:vertical`, `QScrollBar:horizontal` | 滚动条轨道和滑块 |
| `QScrollBar::handle:vertical` | 可拖动的垂直滚动条滑块 |
| `QTabWidget::pane` | 标签页内容周围的面板区域 |
| `QTabBar::tab` | 单个标签标签页 |
| `QFrame` | 带框架的容器，包括预览框 |
| `QLabel` | 静态文本标签 |
| `QCheckBox` | 设置中的复选框 |
| `QToolTip` | 悬停提示 |

例如，让滚动条滑块变宽：

```css
QScrollBar::handle:vertical {
    min-height: 40px;
    background: rgb(108, 92, 231);
    border-radius: 4px;
}
```

或者给所有框架加上圆角：

```css
QFrame {
    border-radius: 8px;
}
```

Qt 样式表支持大多数常见 CSS 属性，包括 `color`、`background`、`border`、`border-radius`、`padding`、`margin` 和 `font-size`。如果某条规则没有生效，尝试让选择器更具体，或在必要时谨慎使用 `!important`。
