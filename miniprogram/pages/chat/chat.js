// pages/chat/chat.js
const api = require('../../utils/api');

Page({
  data: {
    messages: [],
    userInput: '',
    isLoading: false,
    scrollToMessage: '',
    pendingSessionId: null  // 待确认的会话 ID
  },

  onLoad(options) {
    // 如果有初始输入，自动发送
    if (options.input) {
      const input = decodeURIComponent(options.input);
      this.setData({ userInput: input });
      // 延迟一下再发送，让页面先渲染
      setTimeout(() => {
        this.sendMessage(input);
      }, 500);
    }
  },

  // 返回上一页
  onBack() {
    wx.navigateBack();
  },

  // 清空对话
  onClear() {
    wx.showModal({
      title: '提示',
      content: '确定要清空对话记录吗？',
      success: (res) => {
        if (res.confirm) {
          this.setData({ messages: [], pendingSessionId: null });
          wx.showToast({
            title: '已清空',
            icon: 'success'
          });
        }
      }
    });
  },

  // 快速输入
  onQuickInput(e) {
    const { text } = e.currentTarget.dataset;
    this.setData({ userInput: text });
  },

  // 输入事件
  onInput(e) {
    this.setData({
      userInput: e.detail.value
    });
  },

  // 提交事件
  onSubmit() {
    const { userInput, isLoading, pendingSessionId } = this.data;
    if (!userInput || !userInput.trim() || isLoading) {
      return;
    }

    // 有待确认方案时，路由到多轮对话端点（v2.2 多轮）
    if (pendingSessionId) {
      this.sendContinueMessage(userInput);
      return;
    }

    this.sendMessage(userInput);
  },

  // 发送消息
  async sendMessage(content) {
    // 添加用户消息
    const userMessage = {
      id: Date.now(),
      role: 'user',
      type: 'text',
      content: content,
      timeStr: this.formatTime(new Date())
    };

    this.setData({
      messages: [...this.data.messages, userMessage],
      userInput: '',
      isLoading: true,
      scrollToMessage: 'msg-bottom'
    });

    // 添加加载消息
    const loadingMessage = {
      id: Date.now() + 1,
      role: 'assistant',
      type: 'loading',
      content: '正在为你规划行程...'
    };

    this.setData({
      messages: [...this.data.messages, loadingMessage],
      scrollToMessage: 'msg-bottom'
    });

    try {
      // 调用 API
      const result = await api.executeAgent(content);

      // 移除加载消息
      const messages = this.data.messages.filter(m => m.type !== 'loading');

      if (result.status === 'waiting_confirmation') {
        // 方案待确认：显示预览卡片 + 确认按钮
        const planMessage = {
          id: Date.now() + 2,
          role: 'assistant',
          type: 'plan_confirm',
          status: 'waiting_confirmation',
          statusText: '方案已生成',
          summary: result.planSummary || '行程方案已就绪',
          tasks: result.tasks || [],
          route: result.route || null,
          story: result.story || null,
          sessionId: result.sessionId,
          timeStr: this.formatTime(new Date())
        };

        this.setData({
          messages: [...messages, planMessage],
          isLoading: false,
          pendingSessionId: result.sessionId,
          scrollToMessage: 'msg-bottom'
        });
      } else {
        // 直接返回最终结果（非确认流程）
        const planMessage = {
          id: Date.now() + 2,
          role: 'assistant',
          type: 'plan',
          status: result.status,
          statusText: this.getStatusText(result.status),
          summary: `共 ${(result.tasks || []).length} 项任务`,
          tasks: result.tasks || [],
          planId: result.sessionId,
          timeStr: this.formatTime(new Date())
        };

        const notificationMessage = {
          id: Date.now() + 3,
          role: 'assistant',
          type: 'text',
          content: result.notification || '任务执行完成，点击查看详情查看完整行程',
          timeStr: this.formatTime(new Date())
        };

        this.setData({
          messages: [...messages, planMessage, notificationMessage],
          isLoading: false,
          scrollToMessage: 'msg-bottom'
        });
      }

    } catch (err) {
      console.error('请求失败:', err);

      // 移除加载消息，添加错误消息
      const messages = this.data.messages.filter(m => m.type !== 'loading');
      const errorMessage = {
        id: Date.now() + 2,
        role: 'assistant',
        type: 'text',
        content: '抱歉，服务暂时不可用，请稍后重试。',
        timeStr: this.formatTime(new Date())
      };

      this.setData({
        messages: [...messages, errorMessage],
        isLoading: false,
        scrollToMessage: 'msg-bottom'
      });
    }
  },

  // ===== v2.2 多轮对话分发 =====
  async sendContinueMessage(content) {
    const userMessage = {
      id: Date.now(),
      role: 'user',
      type: 'text',
      content: content,
      timeStr: this.formatTime(new Date())
    };
    const loadingMessage = {
      id: Date.now() + 1,
      role: 'assistant',
      type: 'loading',
      content: '正在调整方案...'
    };

    this.setData({
      messages: [...this.data.messages, userMessage, loadingMessage],
      userInput: '',
      isLoading: true,
      scrollToMessage: 'msg-bottom'
    });

    try {
      const result = await api.continueConversation(content, this.data.pendingSessionId);
      const messages = this.data.messages.filter(m => m.type !== 'loading');

      switch (result.status) {
        case 'plan_modified':
          this._handlePlanModified(messages, result);
          break;
        case 'plan_modify_failed':
          this._handlePlanModifyFailed(messages, result);
          break;
        case 'replanned':
          this._handleReplanned(messages, result);
          break;
        case 'conversation_continued':
        default:
          this._handleChatReply(messages, result);
          break;
      }
    } catch (err) {
      console.error('多轮对话失败:', err);
      const messages = this.data.messages.filter(m => m.type !== 'loading');
      this.setData({
        messages: [...messages, {
          id: Date.now() + 2,
          role: 'assistant',
          type: 'text',
          content: '抱歉，多轮对话服务暂时不可用。',
          timeStr: this.formatTime(new Date())
        }],
        isLoading: false,
        scrollToMessage: 'msg-bottom'
      });
    }
  },

  // plan_modified：本地 patch 最近一张 plan_confirm 卡，并标记 diff
  _handlePlanModified(messages, result) {
    const updated = this._applyPlanDiff(messages, result);
    const summary = result.planSummary || '已为你更新方案。';
    const replyMessage = {
      id: Date.now() + 2,
      role: 'assistant',
      type: 'text',
      content: summary,
      timeStr: this.formatTime(new Date())
    };
    this.setData({
      messages: [...updated, replyMessage],
      isLoading: false,
      pendingSessionId: result.sessionId || this.data.pendingSessionId,
      scrollToMessage: 'msg-bottom'
    });
    // 3 秒后清除 diff 颜色态，避免视觉残留
    setTimeout(() => this._clearDiffState(), 3000);
  },

  // plan_modify_failed：渲染错误卡（reason_code + suggestions）
  _handlePlanModifyFailed(messages, result) {
    const entry = (result.changeLog || [])[0] || {};
    const errorMessage = {
      id: Date.now() + 2,
      role: 'assistant',
      type: 'error',
      reasonCode: entry.reason_code || 'unknown',
      reasonLabel: this._errorReasonLabel(entry.reason_code),
      errorText: entry.message || result.reply || '修改失败',
      suggestions: Array.isArray(entry.suggestions) ? entry.suggestions : [],
      timeStr: this.formatTime(new Date())
    };
    this.setData({
      messages: [...messages, errorMessage],
      isLoading: false,
      scrollToMessage: 'msg-bottom'
    });
  },

  // replanned：整张 plan 重做 → 替换最近一张 plan_confirm 卡
  _handleReplanned(messages, result) {
    const tagged = this._tagTasks(result.tasks || [], {});
    const newCard = {
      id: Date.now() + 2,
      role: 'assistant',
      type: 'plan_confirm',
      status: 'waiting_confirmation',
      statusText: '方案已更新',
      summary: result.planSummary || '已重新规划',
      tasks: tagged,
      route: result.route || null,
      story: result.story || null,
      sessionId: result.sessionId,
      timeStr: this.formatTime(new Date())
    };
    const filtered = messages.filter(m => m.type !== 'plan_confirm');
    this.setData({
      messages: [...filtered, newCard],
      isLoading: false,
      pendingSessionId: result.sessionId || this.data.pendingSessionId,
      scrollToMessage: 'msg-bottom'
    });
  },

  // conversation_continued / 兜底：普通对话回复
  _handleChatReply(messages, result) {
    const replyMessage = {
      id: Date.now() + 2,
      role: 'assistant',
      type: 'text',
      content: result.reply || result.planSummary || '收到了～',
      timeStr: this.formatTime(new Date())
    };
    this.setData({
      messages: [...messages, replyMessage],
      isLoading: false,
      scrollToMessage: 'msg-bottom'
    });
  },

  // 把 result.tasks 替换进最近一张 plan_confirm，并按 change_log 打 _diffState
  _applyPlanDiff(messages, result) {
    const diffMap = this._buildDiffMap(result.changeLog || []);
    const newTasks = this._tagTasks(result.tasks || [], diffMap);
    const out = [];
    let patched = false;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (!patched && m.type === 'plan_confirm') {
        out.unshift({
          ...m,
          tasks: newTasks,
          summary: result.planSummary || m.summary,
          route: result.route || m.route
        });
        patched = true;
      } else {
        out.unshift(m);
      }
    }
    return out;
  },

  _buildDiffMap(changeLog) {
    const map = {};
    (changeLog || []).forEach(entry => {
      if (!entry || typeof entry !== 'object') return;
      if (entry.type === 'replace' && entry.task_id) {
        map[entry.task_id] = 'replaced';
      } else if (entry.type === 'insert' && entry.task_id) {
        map[entry.task_id] = 'inserted';
      } else if (entry.type === 'shift_time') {
        // 时移没有具体 task_id；统一打 yellow
        map['__shift__'] = 'shifted';
      }
      // remove / preference_noted 不需要在 result.tasks 里 mark — 已不在
    });
    return map;
  },

  _tagTasks(tasks, diffMap) {
    return (tasks || []).map(t => ({
      ...t,
      _diffState: diffMap[t.task_id] || (diffMap.__shift__ ? 'shifted' : '')
    }));
  },

  _clearDiffState() {
    const cleared = this.data.messages.map(m => {
      if (m.type !== 'plan_confirm' || !Array.isArray(m.tasks)) return m;
      return { ...m, tasks: m.tasks.map(t => ({ ...t, _diffState: '' })) };
    });
    this.setData({ messages: cleared });
  },

  _errorReasonLabel(code) {
    const map = {
      no_candidate: '找不到候选',
      busy_hours: '营业时间',
      over_budget: '超预算',
      location_mismatch: '目标不明',
      unknown: '未识别'
    };
    return map[code] || '操作失败';
  },

  // 点击错误建议 chip → 回填到输入框
  onSuggestionTap(e) {
    const { hint } = e.currentTarget.dataset;
    if (!hint) return;
    this.setData({ userInput: hint });
  },

  // 获取状态文本
  getStatusText(status) {
    const statusMap = {
      'success': '规划完成',
      'partial': '部分完成',
      'error': '执行失败',
      'replan_needed': '重新规划中'
    };
    return statusMap[status] || status;
  },

  // 格式化时间
  formatTime(date) {
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  },

  // 查看行程详情
  onViewPlan(e) {
    const { id } = e.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/plan/plan?id=${id}`
    });
  },

  // 确认方案
  async onConfirmPlan() {
    const { pendingSessionId } = this.data;
    if (!pendingSessionId) return;

    this.setData({ isLoading: true });

    try {
      const result = await api.confirmPlan(pendingSessionId, true);

      // 移除待确认卡片，添加执行结果
      const messages = this.data.messages.filter(m => m.type !== 'plan_confirm');

      const planMessage = {
        id: Date.now(),
        role: 'assistant',
        type: 'plan',
        status: result.status,
        statusText: this.getStatusText(result.status),
        summary: `共 ${(result.tasks || []).length} 项任务`,
        tasks: result.tasks || [],
        planId: pendingSessionId,
        timeStr: this.formatTime(new Date())
      };

      const shareText = result.shareText || '行程已安排好！';
      const notificationMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        type: 'text',
        content: shareText,
        timeStr: this.formatTime(new Date())
      };

      // 缓存行程数据供 plan 页面使用
      const cachedTasks = (result.tasks || []).map(t => {
        const taskResult = (result.results || {})[t.task_id] || {};
        return {
          taskId: t.task_id,
          name: t.name,
          status: t.status || 'SUCCESS',
          result: taskResult
        };
      });
      wx.setStorageSync(`plan_${pendingSessionId}`, {
        status: result.status,
        tasks: cachedTasks,
        notification: shareText
      });

      this.setData({
        messages: [...messages, planMessage, notificationMessage],
        isLoading: false,
        pendingSessionId: null,
        scrollToMessage: 'msg-bottom'
      });

    } catch (err) {
      console.error('确认失败:', err);
      wx.showToast({ title: '确认失败，请重试', icon: 'none' });
      this.setData({ isLoading: false });
    }
  },

  // 取消方案
  async onCancelPlan() {
    const { pendingSessionId } = this.data;
    if (!pendingSessionId) return;

    this.setData({ isLoading: true });

    try {
      await api.confirmPlan(pendingSessionId, false);

      const messages = this.data.messages.filter(m => m.type !== 'plan_confirm');
      const cancelMessage = {
        id: Date.now(),
        role: 'assistant',
        type: 'text',
        content: '好的，已取消本次规划。有需要随时告诉我～',
        timeStr: this.formatTime(new Date())
      };

      this.setData({
        messages: [...messages, cancelMessage],
        pendingSessionId: null,
        isLoading: false,
        scrollToMessage: 'msg-bottom'
      });
    } catch (err) {
      console.error('取消失败:', err);
      // 即使请求失败也清除本地状态
      const messages = this.data.messages.filter(m => m.type !== 'plan_confirm');
      this.setData({
        messages: [...messages, {
          id: Date.now(),
          role: 'assistant',
          type: 'text',
          content: '好的，已取消本次规划。',
          timeStr: this.formatTime(new Date())
        }],
        pendingSessionId: null,
        isLoading: false
      });
    }
  }
});
