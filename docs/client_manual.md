<p><span style="border: 1px solid black;">保密</span></p>

# <center>ImageLabelTS 客户端使用手册</center>

***

## 1. 下载客户端

访问以下地址以下载客户端压缩包：
```
pass
```

## 2. 解压客户端

在桌面新建一个文件夹，并将下载的压缩包解压至该文件夹。
解压后，文件夹应该包含以下内容：
```
ImageLabelTS_sys.client/
    ImageLabelTS.client.exe
    server.crt
    config.json
```

**至此，安装完成。**

## 3. 打开命令行窗口

打开你刚刚创建的文件夹，在里面按住`Shift`，然后点击右键，在打开的菜单中选择`在此处打开PowerShell窗口(S)`

## 4. 客户端操作说明

该程序是一个命令行程序，其命令用法如下：
```cmd
.\ImageLabelTS.client.exe [参数]
```
> [!TIP]
> 当你输入`.\ImageL`后按`Tab`就可以自动补全了~

## 4.1 登录

在首次使用时，需要执行登录操作：
```cmd
.\ImageLabelTS.client.exe login <用户名>
```
用户名就是你自己的中文名字。

在登录成功后，你可以看到一个`.annotator_name`文件，该文件记录了你的用户名，以后客户端会自动读取该文件。

## 4.2 从服务器拉取图片
在登录后，需要从服务器拉取图片：
```cmd
.\ImageLabelTS.client.exe pull
```

该命令会拉取你任务之内的图片和你已经标注的json文件，并保存在workshop文件夹下。

当教师对你执行改派等操作时，也需要重新拉取。

## 4.3 将标注结果推送至服务器

当你完成了标注，需要将标注结果推送至服务器：
```cmd
.\ImageLabelTS.client.exe push
```

该命令会将你本地的workshop文件夹下所有的json文件推送至服务器。

## 5. 注意事项
### 5.1 证书更换
当要求更换证书时，你需要立即将我们提供的新证书文件`server.crt`覆盖掉原有的`server.crt`。

### 5.2 服务器例行维护
服务器每天都会进行例行维护与日志审计，期间服务端可能不稳定/不可用。
维护时间另行通知。

### 5.3 服务器地址变更
服务器地址可能会变更，当被要求更换服务器地址时，你需要修改`config.json`文件中的`server_url`字段。

以上。
*<div style="text-align: right;">黄浦巍<br>2026年4月30日</div>*