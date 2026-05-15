# Maven 安装脚本
# 以管理员权限运行此脚本

Write-Host "=" * 60
Write-Host "  Maven 安装脚本"
Write-Host "=" * 60

# Maven 版本
$mavenVersion = "3.9.6"
$mavenUrl = "https://archive.apache.org/dist/maven/maven-3/$mavenVersion/binaries/apache-maven-$mavenVersion-bin.zip"
$installDir = "C:\Program Files\Maven"
$zipFile = "$env:TEMP\maven.zip"

Write-Host "`n[1/4] 下载 Maven $mavenVersion..."
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $mavenUrl -OutFile $zipFile -UseBasicParsing
    Write-Host "下载完成: $zipFile"
} catch {
    Write-Host "下载失败: $_"
    exit 1
}

Write-Host "`n[2/4] 解压 Maven..."
try {
    if (Test-Path $installDir) {
        Remove-Item -Recurse -Force $installDir
    }
    Expand-Archive -Path $zipFile -DestinationPath "C:\Program Files"
    Rename-Item "C:\Program Files\apache-maven-$mavenVersion" $installDir
    Write-Host "解压完成: $installDir"
} catch {
    Write-Host "解压失败: $_"
    exit 1
}

Write-Host "`n[3/4] 配置环境变量..."
try {
    $mavenHome = $installDir
    $mavenBin = "$mavenHome\bin"

    # 添加到 PATH
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$mavenBin*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$mavenBin", "User")
        Write-Host "已添加到 PATH: $mavenBin"
    } else {
        Write-Host "PATH 已包含 Maven"
    }

    # 设置 MAVEN_HOME
    [Environment]::SetEnvironmentVariable("MAVEN_HOME", $mavenHome, "User")
    Write-Host "已设置 MAVEN_HOME: $mavenHome"
} catch {
    Write-Host "配置环境变量失败: $_"
    exit 1
}

Write-Host "`n[4/4] 清理临时文件..."
Remove-Item -Force $zipFile -ErrorAction SilentlyContinue

Write-Host "`n" + "=" * 60
Write-Host "  Maven 安装完成！"
Write-Host "=" * 60
Write-Host "`n请重新打开命令行窗口，然后运行以下命令验证安装:"
Write-Host "  mvn --version"
Write-Host "`n注意: 需要重新打开窗口才能使环境变量生效"
