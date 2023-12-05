#include <iostream>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <fcntl.h>
// #include <jsoncpp/json/json.h>
#include "json.hpp"
#include <fstream>
#include <thread>
#include <chrono>
#include <unistd.h>

using json::JSON;

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

// Json::Value
JSON readJsonFile(const std::string &filename)
{
    std::ifstream file(filename, std::ifstream::binary);
    if (!file.is_open())
    {
        std::cerr << "Error: Unable to open file " << filename << std::endl;
        return JSON::Load("{}"); // Empty JSON object
    }

    // Get the content of the file
    std::string content((std::istreambuf_iterator<char>(file)),
                        (std::istreambuf_iterator<char>()));

    // std::cout << "Content: " << content << std::endl;

    // Parse the content
    // TODO: Use the stream directly instead of copying the content?
    JSON obj = JSON::Load(content);

    return obj;
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
    const int readRateHertz = 5;

    while (true)
    {
        int fd = tryGetLock(lockName);
        if (fd != -1)
        {
            // Clear the terminal before displaying the data
            std::cout << "\033[2J\033[1;1H";

            // Json::Value jsonData =
            JSON obj = readJsonFile(jsonFilename);

            // // Display the data
            // std::cout << "Data: " << std::endl;
            // std::cout << obj << std::endl;

            // Try to iterate over the nodes and display their names
            std::cout << "Nodes: " << std::endl;
            for (auto &node : obj["__nds"].ObjectRange())
            {
                std::cout << node.first << " : " << node.second["__n"] << std::endl;
            }

            std::cout << "Services: " << std::endl;
            for (auto &service : obj["__srv"].ArrayRange())
            {
                std::cout << service["__dst"] << " -> " << service["__dst"] << ": ";
                for (auto &property :service.ObjectRange())
                {
                    // if start with __, it's a special property
                    if (property.first.find("__") == 0)
                        continue;
                    // std::cout << property.first << " : " << property.second << std::endl;
                    std::cout << property.first << std::endl;
                }
            }

            std::cout << "Topics: " << std::endl;
            for (auto &topic : obj.ObjectRange())
            {
                // if start with __, it's a special property
                if (topic.first.find("__") == 0)
                    continue;
                std::cout << topic.first << " ("<< topic.second["__r"] << " Hz)" << std::endl;
            }


            // Save the object to a local file
            std::ofstream file("data.json");
            file << obj.dump(1, "", ",", ":", false);
            file.close();

            releaseLock(fd, lockName);
        }

        // Wait for the next iteration
        std::this_thread::sleep_for(std::chrono::milliseconds(1000 / readRateHertz));
    }
}
