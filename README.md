# AutoCAD 批量文字替换工具 (CADReplacerApp)

Windows 桌面 GUI 应用程序，通过 COM 自动化驱动 AutoCAD，对 DWG 文件中的文字进行批量查找替换。

## 功能

- 🔍 **查找替换规则** — 支持多条规则同时执行，支持正则表达式和区分大小写
- 📂 **批量处理** — 一次选择多个 DWG 文件，自动逐个处理
- 📝 **多种文字类型** — 普通文字 (AcDbText)、多行文字 (AcDbMText)、块属性 (AcDbAttribute)
- 🧱 **嵌套块支持** — 递归处理嵌套块参照内部的所有实体
- 📐 **布局空间** — 可选择同时处理图纸空间（布局）
- ↩ **撤销功能** — 支持撤销上次替换操作
- 📊 **匹配统计** — 处理前先统计匹配数量
- ⚙️ **配置持久化** — 规则和范围设置自动保存到 config.json

## 系统要求

- **操作系统**: Windows（AutoCAD COM 自动化仅支持 Windows）
- **Python**: 3.10+
- **AutoCAD**: 已安装并可运行
- **依赖**: PySide6, pywin32

## 安装

```bash
# 克隆仓库
git clone <repo-url>
cd CADReplacerApp

# 安装依赖
pip install -r requirements.txt

# （可选）复制并编辑配置文件
cp config.example.json config.json
```

## 使用

```bash
# 启动应用
python run.py
```

### 基本操作流程

1. 在"查找"和"替换"输入框中填写内容，点击 **添加规则**
2. 勾选需要的替换范围（普通文字 / 多行文字 / 块属性 / 嵌套块 / 布局）
3. 点击 **添加文件** 选择要处理的 DWG 文件
4. 点击 **统计** 预览匹配数量
5. 点击 **开始替换** 执行批量替换

## 打包为 EXE

```bash
pip install pyinstaller
python -m PyInstaller CADReplacerAPP.spec
```

生成的 EXE 位于 `dist/` 目录。

## 项目结构

```
CADReplacerApp/
├── run.py                  # 启动脚本
├── src/                    # V2 源码（MVP 架构）
│   ├── main.py             # 应用入口
│   ├── model.py            # 数据模型
│   ├── view.py             # PySide6 GUI
│   ├── presenter.py        # 业务逻辑
│   ├── cad_worker.py       # AutoCAD COM 工作线程
│   └── config.py           # 配置持久化
├── tests/                  # 单元测试
├── pictures/               # 图片资源
├── help_file/              # 帮助文档
├── CADReplacerAPP.spec     # PyInstaller 打包配置
├── requirements.txt        # Python 依赖
└── config.example.json     # 配置文件模板
```

## 架构

采用 **MVP (Model-View-Presenter)** 模式：

- **Model** (`src/model.py`) — 数据类和状态管理
- **View** (`src/view.py`) — PySide6 GUI，实现 IMainView 接口
- **Presenter** (`src/presenter.py`) — 业务逻辑编排，连接 View 和 Model
- **CAD Worker** (`src/cad_worker.py`) — 在独立线程中通过 COM 自动化操作 AutoCAD

## 许可证

MIT License
