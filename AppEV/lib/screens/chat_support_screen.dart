import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../constants/app_colors.dart';

/// Chat Support Screen — AI Bot powered by CustomerService microservice.
/// Creates tickets via ChargingPlatform API through the bot's escalate endpoint.
class ChatSupportScreen extends StatefulWidget {
  const ChatSupportScreen({super.key});

  @override
  State<ChatSupportScreen> createState() => _ChatSupportScreenState();
}

class _ChatSupportScreenState extends State<ChatSupportScreen> with TickerProviderStateMixin {
  final TextEditingController _msgController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<_ChatMessage> _messages = [];

  String? _sessionId;
  String? _currentCategory;
  bool _isTyping = false;
  List<_QuickAction> _quickActions = [];

  /// Bot API base URL — derives from the main API base URL
  String get _botBaseUrl {
    const envUrl = String.fromEnvironment('BOT_BASE_URL', defaultValue: '');
    if (envUrl.isNotEmpty) return envUrl;
    // Derive from API_BASE_URL: replace port 8000 with 8001, remove /api
    const apiUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
    if (apiUrl.isNotEmpty) {
      final uri = Uri.parse(apiUrl);
      return '${uri.scheme}://${uri.host}:8001';
    }
    // Web: use localhost; Native (Android emulator): use 10.0.2.2
    if (kIsWeb) return 'http://localhost:8001';
    return 'http://10.0.2.2:8001';
  }

  @override
  void initState() {
    super.initState();
    _fetchWelcome();
  }

  @override
  void dispose() {
    _msgController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 150), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // ─── API Calls ───

  Future<void> _fetchWelcome() async {
    setState(() => _isTyping = true);
    try {
      final res = await http.post(Uri.parse('$_botBaseUrl/api/bot/welcome'));
      final data = jsonDecode(res.body);
      if (data['success'] == true) {
        final d = data['data'];
        setState(() {
          _messages.add(_ChatMessage(
            text: d['message'] ?? 'Welcome! How can I help you?',
            isBot: true,
          ));
          _quickActions = (d['categories'] as List? ?? [])
              .map((c) => _QuickAction(
                    id: c['id'] ?? '',
                    label: c['label'] ?? c['name'] ?? '',
                  ))
              .toList();
        });
      }
    } catch (e) {
      setState(() {
        _messages.add(_ChatMessage(
          text: '👋 Welcome to PlagSini Support! I\'m here to help.\n\nYou can ask me anything about charging, payments, or account issues.',
          isBot: true,
        ));
      });
    }
    setState(() => _isTyping = false);
    _scrollToBottom();
  }

  Future<void> _selectCategory(String categoryId) async {
    _currentCategory = categoryId;
    setState(() => _isTyping = true);
    try {
      final res = await http.post(
        Uri.parse('$_botBaseUrl/api/bot/category'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'category_id': categoryId}),
      );
      final data = jsonDecode(res.body);
      if (data['success'] == true) {
        final d = data['data'];
        setState(() {
          _messages.add(_ChatMessage(
            text: d['message'] ?? 'Here are some common questions:',
            isBot: true,
          ));
          _quickActions = (d['questions'] as List? ?? [])
              .map((q) => _QuickAction(
                    id: '', // will send as chat
                    label: q.toString(),
                  ))
              .toList();
        });
      }
    } catch (_) {
      setState(() {
        _messages.add(_ChatMessage(text: 'Sorry, I couldn\'t load that category. Try again.', isBot: true));
      });
    }
    setState(() => _isTyping = false);
    _scrollToBottom();
  }

  Future<void> _sendMessage(String text) async {
    if (text.trim().isEmpty) return;
    _msgController.clear();

    setState(() {
      _messages.add(_ChatMessage(text: text, isBot: false));
      _isTyping = true;
      _quickActions = [];
    });
    _scrollToBottom();

    try {
      final res = await http.post(
        Uri.parse('$_botBaseUrl/api/bot/chat'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'message': text,
          'session_id': _sessionId,
          'category': _currentCategory,
        }),
      );
      final data = jsonDecode(res.body);
      if (data['success'] == true) {
        final d = data['data'];
        _sessionId = d['session_id'];

        setState(() {
          _messages.add(_ChatMessage(text: d['message'] ?? '', isBot: true));

          // Show quick action suggestions from bot
          final suggestions = d['suggestions'] as List?;
          if (suggestions != null && suggestions.isNotEmpty) {
            _quickActions = suggestions.map((s) {
              final str = s.toString();
              if (str.toLowerCase().contains('ticket')) {
                return _QuickAction(id: '__ticket__', label: '📩 $str');
              } else if (str.toLowerCase().contains('categor')) {
                return _QuickAction(id: '__show_categories__', label: str);
              }
              return _QuickAction(id: '', label: str);
            }).toList();
          }

          // Show questions if provided
          if (d['questions'] != null) {
            _quickActions = (d['questions'] as List)
                .map((q) => _QuickAction(id: '', label: q.toString()))
                .toList();
          }

          // Auto-open ticket dialog on escalation
          if (d['needs_ticket'] == true) {
            Future.delayed(const Duration(milliseconds: 500), _showTicketDialog);
          }
        });
      }
    } catch (_) {
      setState(() {
        _messages.add(_ChatMessage(text: 'Sorry, something went wrong. Please try again.', isBot: true));
      });
    }
    setState(() => _isTyping = false);
    _scrollToBottom();
  }

  Future<void> _createTicket(String email, String name, String subject, String desc) async {
    setState(() => _isTyping = true);
    try {
      final res = await http.post(
        Uri.parse('$_botBaseUrl/api/bot/escalate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'name': name,
          'subject': subject,
          'description': desc,
          'category': _currentCategory ?? 'general',
        }),
      );
      final data = jsonDecode(res.body);
      if (data['success'] == true) {
        setState(() {
          _messages.add(_ChatMessage(
            text: '✅ **Ticket Created!**\n\n'
                '📋 ${data['data']?['ticket_number'] ?? 'N/A'}\n'
                '📧 Confirmation sent to $email\n\n'
                'Our team will respond soon!',
            isBot: true,
          ));
        });
      } else {
        setState(() {
          _messages.add(_ChatMessage(text: '❌ Failed to create ticket. Please try again.', isBot: true));
        });
      }
    } catch (_) {
      setState(() {
        _messages.add(_ChatMessage(text: '❌ Network error. Please try again later.', isBot: true));
      });
    }
    setState(() => _isTyping = false);
    _scrollToBottom();
  }

  void _showTicketDialog() {
    final auth = Provider.of<AuthProvider>(context, listen: false);
    final emailCtrl = TextEditingController(text: auth.currentUser?.email ?? '');
    final nameCtrl = TextEditingController(text: auth.currentUser?.name ?? '');
    final subjectCtrl = TextEditingController();
    final descCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12192B),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(children: [
          Icon(Icons.confirmation_number, color: AppColors.primaryGreen, size: 22),
          const SizedBox(width: 8),
          const Text('Create Support Ticket', style: TextStyle(fontSize: 18, color: Colors.white)),
        ]),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildDialogField('Email', emailCtrl, Icons.email),
              const SizedBox(height: 10),
              _buildDialogField('Name', nameCtrl, Icons.person),
              const SizedBox(height: 10),
              _buildDialogField('Subject', subjectCtrl, Icons.subject),
              const SizedBox(height: 10),
              _buildDialogField('Describe your issue', descCtrl, Icons.description, maxLines: 4),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primaryGreen,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () {
              if (emailCtrl.text.isEmpty || subjectCtrl.text.isEmpty || descCtrl.text.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Please fill all required fields'), backgroundColor: Colors.red),
                );
                return;
              }
              Navigator.pop(ctx);
              _createTicket(emailCtrl.text, nameCtrl.text, subjectCtrl.text, descCtrl.text);
            },
            child: const Text('Submit', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _buildDialogField(String hint, TextEditingController ctrl, IconData icon, {int maxLines = 1}) {
    return TextField(
      controller: ctrl,
      maxLines: maxLines,
      style: const TextStyle(color: Colors.white, fontSize: 14),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: TextStyle(color: Colors.white38),
        prefixIcon: maxLines == 1 ? Icon(icon, color: AppColors.primaryGreen, size: 20) : null,
        filled: true,
        fillColor: const Color(0xFF0A0A1A),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.white12)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.white12)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: AppColors.primaryGreen)),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
    );
  }

  // ─── UI ───

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF12192B),
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Row(children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [AppColors.primaryGreen, const Color(0xFF00AA55)]),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Center(child: Text('⚡', style: TextStyle(fontSize: 18))),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('PlagSini Support', style: TextStyle(color: AppColors.primaryGreen, fontSize: 16, fontWeight: FontWeight.bold)),
              Text(_isTyping ? 'typing...' : 'Online', style: TextStyle(color: _isTyping ? Colors.amber : Colors.green, fontSize: 11)),
            ],
          ),
        ]),
        actions: [
          IconButton(
            icon: Icon(Icons.confirmation_number_outlined, color: AppColors.primaryGreen),
            tooltip: 'Create Ticket',
            onPressed: _showTicketDialog,
          ),
        ],
      ),
      body: Column(
        children: [
          // Messages
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              itemCount: _messages.length + (_isTyping ? 1 : 0),
              itemBuilder: (ctx, i) {
                if (i == _messages.length && _isTyping) {
                  return _buildTypingIndicator();
                }
                return _buildMessageBubble(_messages[i]);
              },
            ),
          ),

          // Quick actions
          if (_quickActions.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              color: const Color(0xFF0D0D1A),
              height: 50,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: _quickActions.length,
                separatorBuilder: (_, __) => const SizedBox(width: 6),
                itemBuilder: (ctx, i) {
                  final action = _quickActions[i];
                  return GestureDetector(
                    onTap: () {
                      if (action.id == '__ticket__') {
                        _showTicketDialog();
                      } else if (action.id == '__show_categories__') {
                        _fetchWelcome();
                      } else if (action.id.isNotEmpty) {
                        _selectCategory(action.id);
                      } else {
                        _sendMessage(action.label);
                      }
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        border: Border.all(color: action.id == '__ticket__' ? Colors.amber : AppColors.primaryGreen.withOpacity(0.4)),
                        borderRadius: BorderRadius.circular(20),
                        color: action.id == '__ticket__'
                            ? Colors.amber.withOpacity(0.1)
                            : AppColors.primaryGreen.withOpacity(0.05),
                      ),
                      child: Center(
                        child: Text(
                          action.label,
                          style: TextStyle(
                            color: action.id == '__ticket__' ? Colors.amber : AppColors.primaryGreen,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),

          // Input bar
          Container(
            padding: EdgeInsets.only(
              left: 12,
              right: 8,
              top: 8,
              bottom: MediaQuery.of(context).padding.bottom + 8,
            ),
            decoration: BoxDecoration(
              color: const Color(0xFF12192B),
              border: Border(top: BorderSide(color: Colors.white.withOpacity(0.06))),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _msgController,
                    style: const TextStyle(color: Colors.white, fontSize: 15),
                    decoration: InputDecoration(
                      hintText: 'Type a message...',
                      hintStyle: TextStyle(color: Colors.white30),
                      filled: true,
                      fillColor: const Color(0xFF0A0A1A),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    ),
                    onSubmitted: (t) => _sendMessage(t),
                  ),
                ),
                const SizedBox(width: 6),
                Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(colors: [AppColors.primaryGreen, const Color(0xFF00AA55)]),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: IconButton(
                    icon: const Icon(Icons.send_rounded, color: Colors.black, size: 20),
                    onPressed: () => _sendMessage(_msgController.text),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(_ChatMessage msg) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: msg.isBot ? MainAxisAlignment.start : MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (msg.isBot) ...[
            CircleAvatar(
              radius: 16,
              backgroundColor: AppColors.primaryGreen.withOpacity(0.2),
              child: const Text('⚡', style: TextStyle(fontSize: 14)),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: msg.isBot
                    ? const Color(0xFF12192B)
                    : AppColors.primaryGreen.withOpacity(0.15),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(msg.isBot ? 4 : 16),
                  bottomRight: Radius.circular(msg.isBot ? 16 : 4),
                ),
                border: Border.all(
                  color: msg.isBot
                      ? Colors.white.withOpacity(0.06)
                      : AppColors.primaryGreen.withOpacity(0.25),
                ),
              ),
              child: _buildFormattedText(msg.text, msg.isBot),
            ),
          ),
          if (!msg.isBot) const SizedBox(width: 32),
        ],
      ),
    );
  }

  Widget _buildFormattedText(String text, bool isBot) {
    // Simple markdown: **bold**
    final parts = text.split(RegExp(r'\*\*(.*?)\*\*'));
    if (parts.length <= 1) {
      return Text(text, style: TextStyle(color: isBot ? Colors.white : Colors.white, fontSize: 14, height: 1.5));
    }

    List<TextSpan> spans = [];
    for (int i = 0; i < parts.length; i++) {
      if (i % 2 == 0) {
        spans.add(TextSpan(text: parts[i]));
      } else {
        spans.add(TextSpan(text: parts[i], style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF00FF88))));
      }
    }
    return RichText(text: TextSpan(style: TextStyle(color: Colors.white, fontSize: 14, height: 1.5), children: spans));
  }

  Widget _buildTypingIndicator() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: AppColors.primaryGreen.withOpacity(0.2),
            child: const Text('⚡', style: TextStyle(fontSize: 14)),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFF12192B),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withOpacity(0.06)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: List.generate(3, (i) {
                return TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: 1),
                  duration: Duration(milliseconds: 600 + i * 200),
                  builder: (_, val, child) => Opacity(
                    opacity: 0.3 + (val * 0.7),
                    child: child,
                  ),
                  child: Container(
                    width: 8,
                    height: 8,
                    margin: const EdgeInsets.symmetric(horizontal: 2),
                    decoration: BoxDecoration(
                      color: AppColors.primaryGreen,
                      shape: BoxShape.circle,
                    ),
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatMessage {
  final String text;
  final bool isBot;
  _ChatMessage({required this.text, required this.isBot});
}

class _QuickAction {
  final String id;
  final String label;
  _QuickAction({required this.id, required this.label});
}
