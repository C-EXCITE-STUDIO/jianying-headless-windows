// Version-pinned, process-isolated Windows native export helper.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <chrono>
#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <iterator>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

namespace lvve { struct PersistentDraft; struct Draft; }
namespace lyra {
struct RespStruct;
struct ReqStruct {
  virtual ~ReqStruct() = default;
  std::string service, api;
  long tid = -1;
  bool async = false;
  int flags = 0;
};
struct InitReqStruct : ReqStruct {
  std::string project_id;
  int main_config = -1;
  bool render_track = true, mixed_track = false, float_render = false, reserved = false;
  std::string timeline_name;
  std::shared_ptr<lvve::PersistentDraft> draft;
  InitReqStruct() { service = "ProjectService"; api = "init"; }
};
struct DraftInitReqStruct : ReqStruct {
  int input_kind = 2;
  std::string json;
  std::shared_ptr<lvve::Draft> draft;
  bool option_a = false, option_b = true;
  DraftInitReqStruct() { service = "DraftService"; api = "draftInit"; }
};
}
static_assert(sizeof(lyra::ReqStruct) == 0x58);
static_assert(sizeof(lyra::InitReqStruct) == 0xb0);
static_assert(sizeof(lyra::DraftInitReqStruct) == 0x98);

static std::mutex log_mutex;
static std::atomic<int> relevant_logs{0};
static std::atomic<bool> restore_done{false};
static std::atomic<bool> compile_done{false};
void native_log(const char*, const char* file, int line, const char*, int level,
                const char* format, ...) {
  char buffer[4096]{};
  va_list args;
  va_start(args, format);
  std::vsnprintf(buffer, sizeof(buffer), format ? format : "", args);
  va_end(args);
  if (!std::strstr(buffer, "export") && !std::strstr(buffer, "Export") &&
      !std::strstr(buffer, "restore") && !std::strstr(buffer, "Restore") &&
      !std::strstr(buffer, "ERROR") && !std::strstr(buffer, "error")) return;
  if (std::strstr(buffer, "DraftService::restoreDraft driverRun, callback !"))
    restore_done = true;
  if (std::strstr(buffer, "export_callback: VE_INFO_COMPILE_DONE"))
    compile_done = true;
  if (relevant_logs.fetch_add(1) >= 120) return;
  std::lock_guard<std::mutex> guard(log_mutex);
  std::cerr << "engine_log level=" << level << " line=" << line << " file="
            << (file ? file : "") << " msg=" << buffer << '\n';
}

template <typename T>
T required(HMODULE dll, const char* name) {
  auto address = GetProcAddress(dll, name);
  if (!address) throw std::runtime_error(std::string("symbol missing: ") + name);
  return reinterpret_cast<T>(address);
}

LONG WINAPI report_crash(EXCEPTION_POINTERS* info) {
  std::cerr << "native_project_crash=" << std::hex
            << info->ExceptionRecord->ExceptionCode << " at="
            << reinterpret_cast<std::uintptr_t>(info->ExceptionRecord->ExceptionAddress)
            << std::dec << '\n';
  return EXCEPTION_EXECUTE_HANDLER;
}

int wmain(int argc, wchar_t** argv) {
  SetUnhandledExceptionFilter(report_crash);
  if (argc != 8 || !std::filesystem::is_regular_file(argv[1]) ||
      !std::filesystem::is_regular_file(argv[2])) return 2;
  int stage_timeout = std::stoi(argv[4]);
  if (stage_timeout < 5 || stage_timeout > 43200) return 2;
  const int width = std::stoi(argv[5]), height = std::stoi(argv[6]), fps = std::stoi(argv[7]);
  if (width < 16 || width > 8192 || height < 16 || height > 8192 ||
      fps < 1 || fps > 120) return 2;
  const auto output = std::filesystem::absolute(argv[3]);
  if (output.extension() != L".mp4" || std::filesystem::exists(output) ||
      !std::filesystem::is_directory(output.parent_path())) return 2;
  std::ifstream file(argv[2], std::ios::binary);
  std::string json((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
  if (json.empty()) return 2;
  HMODULE dll = LoadLibraryExW(argv[1], nullptr,
      LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
  if (!dll) return 3;
  try {
    using Deserialize = std::shared_ptr<lvve::PersistentDraft> (*)(const std::string&);
    using Parse = std::shared_ptr<lvve::Draft> (*)(const std::string&);
    using Instance = void* (*)();
    using Startup = void (*)(void*, const void*);
    using OpenSession = long (*)(void*, const void*, const std::string&);
    using PumpOnce = bool (*)(void*);
    using Init = void (*)(std::shared_ptr<void>*, const std::shared_ptr<lyra::InitReqStruct>*, long);
    using GetSession = void (*)(void*, std::shared_ptr<void>*, long);
    using GetWrapper = void (*)(void*, std::shared_ptr<void>*);
    using Invoke = void (*)(void*, std::shared_ptr<void>*, const std::shared_ptr<lyra::ReqStruct>*, long);
    using InvokeSync = void (*)(void*, const std::shared_ptr<lyra::ReqStruct>*,
        const std::function<void(std::shared_ptr<lyra::RespStruct>)>*, long);
    using DraftTransaction = void (*)(void*, std::shared_ptr<lvve::Draft>*,
        const std::function<void(std::shared_ptr<lvve::Draft>)>*, long);
    using Shutdown = void (*)(void*);
    using CloseSession = void (*)(void*, long, const std::function<void()>*);
    using GetLogger = void* (*)();
    using SetAlog = void (*)(void*, decltype(&native_log), void (*)(char, char));
    using SetLogLevel = void (*)(void*, const std::string&);
    auto deserialize = required<Deserialize>(dll,
        "?deserialize_persistent_draft@Deserializer@lvve@@SA?AV?$shared_ptr@VPersistentDraft@lvve@@@std@@AEBV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@4@@Z");
    auto parse = required<Parse>(dll,
        "?GetDraftFromJson@lvve@@YA?AV?$shared_ptr@VDraft@lvve@@@std@@AEBV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@3@@Z");
    auto instance = required<Instance>(dll, "?instance@Server@lyra@@SAPEAU12@XZ");
    auto startup = required<Startup>(dll,
        "?startup@Server@lyra@@QEAAXPEBUVEGlobalConfig@lvve@@@Z");
    auto open_session = required<OpenSession>(dll,
        "?openSession@Server@lyra@@QEAAJPEBUVEAdapterConfig@adapter@lvve@@AEBV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@@Z");
    auto pump_once = required<PumpOnce>(dll, "?pumpOnce@Server@lyra@@QEAA_NXZ");
    auto init = required<Init>(dll,
        "?init@ProjectClient@@SA?AV?$shared_ptr@UInitRespStruct@lyra@@@std@@V?$shared_ptr@UInitReqStruct@lyra@@@3@J@Z");
    auto get_session = required<GetSession>(dll,
        "?getSession@Server@lyra@@QEAA?AV?$shared_ptr@USession@lyra@@@std@@J@Z");
    auto get_wrapper = required<GetWrapper>(dll,
        "?getVeWrapper@Session@lyra@@QEAA?AV?$shared_ptr@UVeWrapper@wrapper@lyra@@@std@@XZ");
    auto invoke = required<Invoke>(dll,
        "?invoke@Server@lyra@@QEAA?AV?$shared_ptr@URespStruct@lyra@@@std@@V?$shared_ptr@UReqStruct@lyra@@@4@J@Z");
    auto invoke_sync = required<InvokeSync>(dll,
        "?invokeSync@Server@lyra@@QEAAXV?$shared_ptr@UReqStruct@lyra@@@std@@AEBV?$function@$$A6AXV?$shared_ptr@URespStruct@lyra@@@std@@@Z@4@J@Z");
    auto draft_transaction = required<DraftTransaction>(dll,
        "?draftTransaction@Session@lyra@@QEAA?AV?$shared_ptr@VDraft@lvve@@@std@@AEBV?$function@$$A6AXV?$shared_ptr@VDraft@lvve@@@std@@@Z@4@J@Z");
    auto shutdown = required<Shutdown>(dll, "?shutdown@Server@lyra@@QEAAXXZ");
    auto close_session = required<CloseSession>(dll,
        "?closeSession@Server@lyra@@QEAAXJV?$function@$$A6AXXZ@std@@@Z");
    auto get_logger = required<GetLogger>(dll, "?getLogger@Logger@lvve@@SAAEAV12@XZ");
    auto set_alog = required<SetAlog>(dll,
        "?setAlogFunction@Logger@lvve@@QEAAXP6AXPEBD0H0H0ZZP6AXDD@Z@Z");
    auto set_log_level = required<SetLogLevel>(dll,
        "?setLogLevel@Logger@lvve@@QEAAXAEBV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@@Z");
    auto logger = get_logger();
    set_alog(logger, native_log, nullptr);
    set_log_level(logger, "debug");
    auto draft = deserialize(json);
    std::cerr << "stage=deserialize result=" << bool(draft) << '\n';
    if (!draft) return 4;
    auto server = instance();
    startup(server, nullptr);
    auto sid = open_session(server, nullptr, "codex-isolated-native-project");
    for (int i = 0; i < 10; ++i) pump_once(server);
    std::cerr << "stage=session sid=" << sid << '\n';
    auto request = std::make_shared<lyra::InitReqStruct>();
    request->project_id = "codex-isolated-native-project";
    request->timeline_name = "codex-isolated-native-project";
    request->draft = draft;
    std::shared_ptr<void> response;
    init(&response, &request, sid);
    std::cerr << "stage=project_init response=" << bool(response) << '\n';
    if (!response) throw std::runtime_error("native project initialization missing response");
    if (response) {
      auto bytes = reinterpret_cast<const unsigned char*>(response.get());
      auto service = reinterpret_cast<const std::string*>(bytes + 0x08);
      auto api = reinterpret_cast<const std::string*>(bytes + 0x28);
      const int code = *reinterpret_cast<const int*>(bytes + 0x4c);
      std::cerr << "response_service=" << *service << " api=" << *api
                << " tid=" << *reinterpret_cast<const int*>(bytes + 0x48)
                << " code=" << code << '\n';
      if (code != 0) throw std::runtime_error("native project initialization failed");
    }
    std::shared_ptr<void> session, wrapper;
    get_session(server, &session, sid);
    if (session) get_wrapper(session.get(), &wrapper);
    std::cerr << "stage=wrapper result=" << bool(wrapper) << '\n';
    auto binding = std::make_shared<lyra::DraftInitReqStruct>();
    binding->tid = 0;
    binding->draft = parse(json);
    if (!binding->draft) return 7;
    std::shared_ptr<lyra::ReqStruct> base_binding = binding;
    std::shared_ptr<void> bind_response;
    invoke(server, &bind_response, &base_binding, sid);
    std::cerr << "stage=draft_init response=" << bool(bind_response) << '\n';
    if (!bind_response) throw std::runtime_error("native draft initialization missing response");
    if (bind_response) {
      auto bytes = reinterpret_cast<const unsigned char*>(bind_response.get());
      auto service = reinterpret_cast<const std::string*>(bytes + 0x08);
      auto api = reinterpret_cast<const std::string*>(bytes + 0x28);
      const int code = *reinterpret_cast<const int*>(bytes + 0x4c);
      std::cerr << "draft_service=" << *service << " api=" << *api
                << " code=" << code << '\n';
      if (code != 0) throw std::runtime_error("native draft initialization failed");
    }
    bind_response.reset(); base_binding.reset(); binding.reset();
    // Version-pinned internal restore client: (session id, restore flag,
    // timeline id). The installed DLL constructs and owns the full request.
    constexpr std::uintptr_t restore_rva = 0x11c41a0;
    using RestoreDraft = void (*)(long, bool, long);
    auto restore_draft = reinterpret_cast<RestoreDraft>(
        reinterpret_cast<std::uintptr_t>(dll) + restore_rva);
    restore_draft(sid, true, 0);
    auto restore_until = std::chrono::steady_clock::now() + std::chrono::seconds(stage_timeout);
    while (!restore_done && std::chrono::steady_clock::now() < restore_until) {
      pump_once(server);
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    std::cerr << "stage=restore_done result=" << bool(restore_done) << '\n';
    if (!restore_done) throw std::runtime_error("native draft restoration timed out");
    std::shared_ptr<lvve::Draft> runtime_draft;
    std::atomic<bool> transaction_called{false};
    std::function<void(std::shared_ptr<lvve::Draft>)> inspect = [&](auto found) {
      transaction_called = true;
      std::cerr << "stage=draft_transaction callback_draft=" << bool(found) << '\n';
    };
    draft_transaction(session.get(), &runtime_draft, &inspect, 0);
    std::cerr << "stage=draft_transaction result=" << bool(runtime_draft)
              << " callback=" << transaction_called << '\n';
    if (!runtime_draft || !transaction_called)
      throw std::runtime_error("native runtime draft unavailable after restoration");
    runtime_draft.reset();
    // This installed DLL contains an internal factory for a fully initialized
    // ExportStartReqStruct at the version-pinned RVA below.
    constexpr std::uintptr_t factory_rva = 0x11b3ac0;
    using ExportRequestFactory = void (*)(std::shared_ptr<void>*);
    auto factory = reinterpret_cast<ExportRequestFactory>(
        reinterpret_cast<std::uintptr_t>(dll) + factory_rva);
    std::shared_ptr<void> export_request;
    factory(&export_request);
    std::cerr << "stage=export_request result=" << bool(export_request) << '\n';
    if (export_request) {
      auto bytes = reinterpret_cast<const unsigned char*>(export_request.get());
      auto service = reinterpret_cast<const std::string*>(bytes + 0x08);
      auto api = reinterpret_cast<const std::string*>(bytes + 0x28);
      auto output_field = reinterpret_cast<const std::string*>(bytes + 0x58);
      std::cerr << "export_service=" << *service << " api=" << *api
                << " output_empty=" << output_field->empty() << '\n';
      if (*service != "ExportService" || *api != "exportStart")
        throw std::runtime_error("native export request identity mismatch");
    }
    if (!export_request) throw std::runtime_error("native export request missing");
    {
      auto bytes = reinterpret_cast<unsigned char*>(export_request.get());
      *reinterpret_cast<int*>(bytes + 0x48) = 0; // timeline id
      *reinterpret_cast<std::string*>(bytes + 0x58) = output.string();
      // The exact pinned Windows request has a 32-byte output string followed
      // by eight bytes of alignment, then the packed ExportConfig.
      auto config = bytes + 0x80;
      int default_width = 0, default_height = 0;
      double default_fps = 0;
      std::memcpy(&default_width, config + 0x3f, sizeof(default_width));
      std::memcpy(&default_height, config + 0x43, sizeof(default_height));
      std::memcpy(&default_fps, config + 0x4a, sizeof(default_fps));
      std::cerr << "stage=export_defaults width=" << default_width
                << " height=" << default_height << " fps=" << default_fps << '\n';
      if (default_width != 0 || default_height != 0 || default_fps != 30)
        throw std::runtime_error("native export configuration layout mismatch");
      const double requested_fps = fps;
      std::memcpy(config + 0x3f, &width, sizeof(width));
      std::memcpy(config + 0x43, &height, sizeof(height));
      std::memcpy(config + 0x4a, &requested_fps, sizeof(requested_fps));
      std::shared_ptr<lyra::ReqStruct> export_base(export_request,
          reinterpret_cast<lyra::ReqStruct*>(export_request.get()));
      std::atomic<int> callback_count{0};
      std::atomic<int> callback_code{0};
      std::function<void(std::shared_ptr<lyra::RespStruct>)> on_export = [&](auto reply) {
        const int count = ++callback_count;
        const int code = reply
            ? *reinterpret_cast<const int*>(reinterpret_cast<const char*>(reply.get()) + 0x4c)
            : -998;
        callback_code = code;
        if (code != 0 || count == 1 || count % 20 == 0)
          std::cerr << "stage=export_callback count=" << count
                    << " code=" << code << '\n';
      };
      std::cerr << "stage=export_submit output=" << output.string() << '\n';
      invoke_sync(server, &export_base, &on_export, sid);
      std::cerr << "stage=export_invoked\n";
      auto until = std::chrono::steady_clock::now() + std::chrono::seconds(stage_timeout);
      // The engine can report a compile error while switching from hardware
      // decode to software decode. Keep pumping until its final completion,
      // a nonzero response, or the bounded stage timeout.
      while (!compile_done && callback_code.load() == 0 &&
             std::chrono::steady_clock::now() < until) {
        pump_once(server);
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
      }
      for (int i = 0; i < 25; ++i) {
        pump_once(server);
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
      }
      auto size = std::filesystem::exists(output) ? std::filesystem::file_size(output) : 0;
      std::cerr << "stage=export_waited bytes=" << size
                << " callbacks=" << callback_count.load() << " callback_code=" << callback_code.load()
                << " compile_done=" << bool(compile_done) << '\n';
      if (!compile_done || callback_code.load() != 0 || size == 0)
        throw std::runtime_error("native export did not complete");
      export_base.reset();
    }
    export_request.reset();
    wrapper.reset(); session.reset();
    bool response_ok = bool(response);
    response.reset(); request.reset(); draft.reset();
    std::atomic<bool> close_done{false};
    std::function<void()> on_close = [&] { close_done = true; };
    close_session(server, sid, &on_close);
    auto close_until = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (!close_done && std::chrono::steady_clock::now() < close_until) {
      pump_once(server);
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    std::cerr << "stage=close_session result=" << close_done << '\n';
    shutdown(server);
    std::cerr << "stage=shutdown\n";
    std::cerr << "stage=free_library_begin\n";
    FreeLibrary(dll);
    std::cerr << "stage=free_library_done\n";
    // The vendor runtime has process-exit worker threads after a restored
    // timeline. End only this isolated helper after native shutdown; the
    // outer Python process independently checks the complete MP4.
    TerminateProcess(GetCurrentProcess(), response_ok ? 0 : 5);
    return 7;
  } catch (const std::exception& error) {
    std::cerr << "native project failed: " << error.what() << '\n';
    // The vendor runtime can leave worker threads alive after export fails.
    // End this isolated helper so its caller receives the failure promptly.
    std::cerr.flush();
    TerminateProcess(GetCurrentProcess(), 6);
    return 6;
  }
}
