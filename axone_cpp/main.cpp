#include <iostream>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <fcntl.h>
#include <jsoncpp/json/json.h>
#include <fstream>
#include <thread>
#include <chrono>
#include <unistd.h>

/*! Try to get lock. Return its file descriptor or -1 if failed.
 *
 *  @param lockName Name of file used as lock (i.e. '/var/lock/myLock').
 *  @return File descriptor of lock file, or -1 if failed.
 */
int tryGetLock(char const *lockName)
{
    mode_t m = umask(0);
    int fd = open(lockName, O_RDWR | O_CREAT, 0666);
    umask(m);
    if (fd >= 0 && flock(fd, LOCK_EX | LOCK_NB) < 0)
    {
        close(fd);
        fd = -1;
    }
    return fd;
}

/*! Release the lock obtained with tryGetLock( lockName ).
 *
 *  @param fd File descriptor of lock returned by tryGetLock( lockName ).
 *  @param lockName Name of file used as lock (i.e. '/var/lock/myLock').
 */
void releaseLock(int fd, char const *lockName)
{
    if (fd < 0)
        return;
    remove(lockName);
    close(fd);
}

Json::Value readJsonFile(const std::string &filename)
{
    std::ifstream file(filename, std::ifstream::binary);
    if (!file.is_open())
    {
        std::cerr << "Error: Unable to open file " << filename << std::endl;
        return Json::Value();
    }

    Json::Value root;
    Json::CharReaderBuilder builder;
    std::string errs;

    if (!Json::parseFromStream(builder, file, &root, &errs))
    {
        std::cerr << "Error: Unable to parse JSON from file " << filename << ": " << errs << std::endl;
        return Json::Value();
    }

    return root;
}

int main(int argc, char *argv[])
{
    if (argc != 2)
    {
        std::cerr << "Error: Invalid number of arguments. Usage: axone_cpp <memory_name>" << std::endl;
        return 1;
    }

    // Load the name of the memory from the command line
    const std::string memoryName = argv[1];
    std::string result = std::string("/home/hexadrone-dev/") + memoryName + std::string(".axone.lock");
    const char *lockName = result.c_str();

    const std::string jsonFilename = "/dev/shm/sm_" + memoryName;
    const int readRateSeconds = 1;

    while (true)
    {
        int fd = tryGetLock(lockName);
        if (fd != -1)
        {
            Json::Value jsonData = readJsonFile(jsonFilename);

            // Clear the terminal before displaying the data
            std::cout << "\033[2J\033[1;1H";

            // Display the data
            std::cout << "Data: " << std::endl;

            Json::StreamWriterBuilder builder;
            builder["commentStyle"] = "None";
            builder["indentation"] = "    "; // remove indentation
            builder["colonSymbol"] = ":";    // set colon separator
            builder["commaSymbol"] = ",";    // set comma separator
            std::unique_ptr<Json::StreamWriter> writer(
                builder.newStreamWriter());
            writer->write(jsonData, &std::cout);
            std::cout << std::endl; // add lf and flush

            // std::cout << out << std::endl;

            releaseLock(fd, lockName);
        }

        std::this_thread::sleep_for(std::chrono::seconds(readRateSeconds));
    }

    return 0;
}